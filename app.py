from flask import Flask, request, jsonify, send_file, g
import os
import json
import uuid
import re
import random
import textwrap
from datetime import datetime
import google.generativeai as genai
from werkzeug.utils import secure_filename
import tempfile

from PyPDF2 import PdfReader
from fpdf import FPDF
import pdfkit
from pydantic import ValidationError
from flask_cors import CORS
from schemas import GenerateQuestionsRequest, ExportPaperRequest, ConvertHtmlRequest

# --- Basic App Configuration ---
def init_app():
    app = Flask(__name__)
    CORS(app)
    app.secret_key = os.urandom(24)
    app.config['UPLOAD_FOLDER'] = '/tmp/uploads/'
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB max file size
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('/tmp/temp_outputs', exist_ok=True)
    return app

app = init_app()

# Model fallback cascade — best quality first, faster fallback on error
MODEL_CASCADE = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-flash-latest",
]

# --- API Configuration ---
def configure_api():
    """Configure Gemini API with dynamic model discovery.
    
    Queries the API to discover all available models and auto-selects the best.
    Get your free API key at: https://aistudio.google.com/app/apikey
    """
    # Use API key strictly from environment variable
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    
    if not GEMINI_API_KEY:
        print("Warning: GEMINI_API_KEY not set in environment.")
    
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)

    # Try dynamic model discovery first
    try:
        from gemini_model_resolver import get_best_model
        model = get_best_model(preferred_tier="pro")
        print(f"✅ Dynamic model discovery: {model.model_name}")
        return model, genai
    except ImportError:
        print("ℹ️  gemini_model_resolver not found, using static cascade")
    except Exception as e:
        print(f"⚠️  Dynamic discovery failed: {e}. Using static cascade.")

    # Static fallback cascade
    for model_name in MODEL_CASCADE:
        try:
            model = genai.GenerativeModel(model_name)
            model.count_tokens("test")
            print(f"✅ Gemini model initialized: {model_name}")
            return model, genai
        except Exception as e:
            print(f"⚠️  Model {model_name} unavailable: {e}. Trying next...")

    # Final fallback
    fallback = MODEL_CASCADE[-1]
    print(f"⚠️  Using fallback model: {fallback}")
    return genai.GenerativeModel(fallback), genai

model, genai = configure_api()

def extract_gemini_file_id(file_uri):
    """Extracts the file ID from a full URI to prevent length errors."""
    if not file_uri:
        return None
    file_id = str(file_uri)
    if "https://" in file_id:
        file_id = file_id.split("/")[-1]
    if not file_id.startswith("files/"):
        file_id = f"files/{file_id}"
    return file_id

# --- File Processing Functions ---
def process_file_to_gemini(file_path, display_name=None):
    """Upload a local file to Gemini API directly."""
    try:
        print(f"Uploading {file_path} to Gemini...")
        gemini_file = genai.upload_file(file_path, display_name=display_name)
        print(f"File uploaded successfully. URI: {gemini_file.uri}")
        return gemini_file.uri
    except Exception as e:
        print(f"Error uploading to Gemini: {e}")
        return None

# --- Question Generation Functions ---
def analyze_content(file_uri, subject_name, fallback_text=None, subject_details=''):
    """Analyze the content to identify topics and potential question areas."""
    if file_uri or fallback_text:
        prompt_text = f"Based on the attached content for the subject '{subject_name}'"
        if subject_details:
             prompt_text += f" (Context & Instructions: {subject_details})"
        prompt_text += ", identify the main topics and subtopics that could be tested in an exam."
        if fallback_text and not file_uri:
            prompt_text = f"CONTENT:\n{fallback_text[:10000]}\n\n" + prompt_text
    else:
        prompt_text = f"Identify the main topics and subtopics for the subject '{subject_name}'"
        if subject_details:
             prompt_text += f" given this context: {subject_details}."
        else:
             prompt_text += " that could be tested in an exam."

    prompt_text += """
    Return the result as a JSON array of objects with the following structure:
    [
        {
            "topic": "Main topic name",
            "subtopics": ["Subtopic 1", "Subtopic 2", ...],
            "importance": "High/Medium/Low",
            "question_types": ["MCQ", "Short Answer", "Essay", ...]
        }
    ]
    
    Ensure the response is valid JSON. Focus on extracting meaningful topics that appear to be significant in the content.
    """
    
    try:
        model_instance = genai.GenerativeModel(getattr(g, 'gemini_model_name', model.model_name))
        
        # Construct the payload
        contents = [prompt_text]
        if file_uri:
            # We must pass the actual `File` object or URI dictionary to the API
            # For latest SDK, we can pass `genai.get_file(file_uri)`
            print(f"Analyzing Gemini Remote File URI: {file_uri}")
            try:
                gemini_file = genai.get_file(extract_gemini_file_id(file_uri))
                contents.insert(0, gemini_file)
            except Exception as fe:
                print(f"Failed to fetch gemini file {file_uri}: {fe}. Attempting text fallback if available.")
                if not fallback_text:
                     raise fe

        response = model_instance.generate_content(contents)
        result = response.text
        
        print(f"Raw response from Gemini API: {result[:100]}...")
        
        # Try to extract JSON from the response
        json_content = None
        
        # Check if response contains JSON enclosed in ```json ... ```
        json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
        if json_match:
            json_content = json_match.group(1).strip()
            
        # If not found in code blocks, try to find JSON array directly
        if not json_content:
            json_match = re.search(r'\[\s*{.*}\s*\]', result, re.DOTALL)
            if json_match:
                json_content = json_match.group(0).strip()
        
        # If still not found, use the entire response
        if not json_content:
            json_content = result.strip()
        
        # Clean the JSON content
        json_content = json_content.replace('\n', ' ')
        json_content = re.sub(r'```.*?```', '', json_content, flags=re.DOTALL)
        
        # Final fallback - if we can't get valid JSON, create a minimal structure
        try:
            topics = json.loads(json_content)
        except json.JSONDecodeError as e:
            print(f"JSON decoding error: {str(e)}")
            print(f"Attempted to parse: {json_content[:100]}...")
            
            # Create a default topic structure using regex to extract topic names
            topic_matches = re.findall(r'topic["\']?\s*:\s*["\']([^"\']+)["\']', result, re.IGNORECASE)
            
            if topic_matches:
                topics = [{"topic": topic, "subtopics": [], "importance": "Medium", "question_types": ["MCQ", "Short Answer"]} for topic in topic_matches]
            else:
                # Create a single generic topic
                topics = [{
                    "topic": f"{subject_name} Concepts",
                    "subtopics": [],
                    "importance": "Medium",
                    "question_types": ["MCQ", "Short Answer", "Essay"]
                }]
        
        return {"success": True, "topics": topics}
        
    except Exception as e:
        print(f"Error analyzing content: {str(e)}")
        return {"success": False, "error": f"Failed to analyze content: {str(e)}"}

def generate_questions(file_uri, params, fallback_text=None):
    """Generate questions based on content and specified parameters."""
    subject = params.get('subject', 'General')
    subject_details = params.get('subject_details', '')
    topics = params.get('topics', [])
    difficulty = params.get('difficulty', 'Medium')
    question_types = params.get('question_types', ['MCQ', 'Short Answer'])
    num_questions = int(params.get('num_questions', 10))
    
    topics_str = ", ".join(topics) if topics else "all covered topics"
    question_types_str = ", ".join(question_types)
    
    prompt_text = f"Generate {num_questions} exam questions for the subject '{subject}' covering {topics_str}."
    if subject_details:
         prompt_text += f"\nSTRICT CONTEXT AND INSTRUCTIONS FOR GENERATION: {subject_details}\n"
         
    if file_uri or fallback_text:
        prompt_text += " Base the questions primarily on the provided content document."
    if fallback_text and not file_uri:
         prompt_text = f"CONTENT:\n{fallback_text[:15000]}\n\n" + prompt_text

    prompt_text += f"""
    Questions should be at {difficulty} difficulty level.
    
    Include the following types of questions: {question_types_str}.
    
    For each question:
    1. Include a clear question statement
    2. For MCQs, provide 4 options with the correct answer marked
    3. For short answer questions, include an expected answer
    4. For essay questions, include key points that should be covered
    5. Add a "topic" field indicating which topic/subtopic this question covers
    6. Add a "difficulty" field with the value: Easy, Medium, or Hard
    7. Add a "type" field indicating the question type (MCQ, Short Answer, Essay, etc.)
    
    Return the questions as a JSON array with this structure:
    [
        {{
            "id": "unique_id",
            "text": "Question text",
            "options": ["Option A", "Option B", "Option C", "Option D"],  // for MCQs
            "correct_answer": "Correct answer or option",
            "explanation": "Explanation of the answer",
            "topic": "Topic/subtopic this covers",
            "difficulty": "Easy/Medium/Hard",
            "type": "MCQ/Short Answer/Essay/etc."
        }}
    ]
    
    Ensure the response is valid JSON. Generate unique and diverse questions that test different aspects of the subject.
    """
    
    try:
        model_instance = genai.GenerativeModel(getattr(g, 'gemini_model_name', model.model_name))

        # Construct payload
        contents = [prompt_text]
        if file_uri:
             try:
                 gemini_file = genai.get_file(extract_gemini_file_id(file_uri))
                 contents.insert(0, gemini_file)
             except Exception as fe:
                 print(f"Failed to fetch gemini file {file_uri} during questions: {fe}")
                 if not fallback_text:
                     raise fe

        response = model_instance.generate_content(contents)
        result = response.text
        
        print(f"Raw questions response from Gemini API: {result[:100]}...")
        
        # Robust RegEx parsing specifically targeting the JSON array, ignoring AI conversational filler
        json_content = None
        
        # Strategy 1: Find standard code block markdown
        json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', result, re.DOTALL | re.IGNORECASE)
        if json_match:
            json_content = json_match.group(1).strip()
            
        # Strategy 2: Greedily capture the largest JSON array directly
        if not json_content:
            json_match = re.search(r'\[\s*{.*?}\s*\]', result, re.DOTALL)
            if json_match:
                json_content = json_match.group(0).strip()
        
        # Fallback Strategy: Complete scrub
        if not json_content:
            json_content = result.strip()
            
        # UNIVERSAL CLEANUP for trailing commas and literal newlines
        if json_content:
            json_content = json_content.replace('\n', ' ')
            json_content = json_content.replace('\r', ' ')
            json_content = re.sub(r',\s*\}', '}', json_content)
            json_content = re.sub(r',\s*\]', ']', json_content)
            
        # Parse the JSON
        try:
            questions = json.loads(json_content)
        except json.JSONDecodeError as e:
            print(f"JSON decoding error for selected questions: {str(e)}")
            print(f"Attempted to parse: {json_content[:500]}...")
            
            # Create fallback questions if JSON parsing fails
            questions = []
            for i in range(min(3, num_questions)):
                questions.append({
                    "id": f"fallback_{i}",
                    "text": f"Generated question could not be parsed. Please regenerate the questions.",
                    "options": ["Option A", "Option B", "Option C", "Option D"] if "MCQ" in question_types else [],
                    "correct_answer": "Option A" if "MCQ" in question_types else "Please regenerate questions",
                    "explanation": "JSON parsing error occurred",
                    "topic": topics[0] if topics else subject,
                    "difficulty": difficulty,
                    "type": question_types[0] if question_types else "Short Answer"
                })
        
        # Ensure each question has a unique ID
        for i, q in enumerate(questions):
            if 'id' not in q or not q['id']:
                q['id'] = f"q_{str(uuid.uuid4())[:8]}"
                
            # Ensure required fields exist
            if 'options' not in q and q.get('type') == 'MCQ':
                q['options'] = ["Option A", "Option B", "Option C", "Option D"]
            
            if 'correct_answer' not in q:
                q['correct_answer'] = "See explanation" if 'explanation' in q else ""
                
            if 'difficulty' not in q:
                q['difficulty'] = difficulty
                
            if 'type' not in q:
                q['type'] = question_types[0] if question_types else "Short Answer"
                
            if 'topic' not in q:
                q['topic'] = topics[0] if topics else subject
        
        return {"success": True, "questions": questions}
    except Exception as e:
        print(f"Error generating questions: {str(e)}")
        return {"success": False, "error": f"Failed to generate questions: {str(e)}"}

def select_questions_from_bank(question_bank, params):
    """Select questions from an existing question bank based on parameters."""
    topics = params.get('topics', [])
    difficulty = params.get('difficulty', 'Medium')
    question_types = params.get('question_types', ['MCQ', 'Short Answer'])
    num_questions = int(params.get('num_questions', 10))
    
    # Filter questions based on criteria
    filtered_questions = question_bank
    
    if topics:
        filtered_questions = [q for q in filtered_questions if q.get('topic') in topics]
    
    if difficulty != 'Any':
        filtered_questions = [q for q in filtered_questions if q.get('difficulty') == difficulty]
    
    if question_types:
        filtered_questions = [q for q in filtered_questions if q.get('type') in question_types]
    
    # Random selection if we have more questions than needed
    if len(filtered_questions) > num_questions:
        selected_questions = random.sample(filtered_questions, num_questions)
    else:
        selected_questions = filtered_questions
    
    return selected_questions

def combine_questions(generated_questions, selected_questions, num_total):
    """Combine generated questions and selected questions."""
    all_questions = generated_questions + selected_questions
    
    # Ensure we don't exceed the requested number
    if len(all_questions) > num_total:
        all_questions = random.sample(all_questions, num_total)
    
    # Sort by topic and type for a better organized paper
    all_questions.sort(key=lambda q: (q.get('topic', ''), q.get('type', '')))
    
    return all_questions

# --- Output Generation Functions ---
def generate_pdf(questions, exam_title, include_answers=False):
    """Generate a PDF file with the questions."""
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Set up fonts
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, exam_title, 0, 1, "C")
        
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", 0, 1, "R")
        pdf.ln(5)
        
        # Add questions
        current_topic = None
        current_type = None
        
        for i, q in enumerate(questions):
            # Skip any invalid question
            if not isinstance(q, dict):
                continue
                
            # Safety check to ensure q is a dictionary with required fields
            q_text = q.get('text', 'Question text missing')
            q_topic = q.get('topic', 'General')
            q_type = q.get('type', 'General')
            q_difficulty = q.get('difficulty', 'Medium')
            
            # Add topic header if it changes
            if q_topic != current_topic:
                current_topic = q_topic
                pdf.set_font("Arial", "B", 14)
                pdf.cell(0, 10, f"Topic: {current_topic}", 0, 1)
                pdf.ln(2)
            
            # Add question type header if it changes
            if q_type != current_type:
                current_type = q_type
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, f"Section: {current_type} Questions", 0, 1)
                pdf.ln(2)
            
            # Add question
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 10, f"Question {i+1} ({q_difficulty} Difficulty)", 0, 1)
            
            pdf.set_font("Arial", "", 10)
            # Split the question text into multiple lines to fit within the PDF width
            # Ensure text is not None before processing
            if q_text:
                wrapped_text = textwrap.fill(q_text, width=85)
                for line in wrapped_text.split('\n'):
                    pdf.cell(0, 8, line, 0, 1)
            else:
                pdf.cell(0, 8, "Question text not available", 0, 1)
            
            # Add options for MCQs
            if q_type == 'MCQ' and 'options' in q and isinstance(q.get('options'), list):
                pdf.ln(2)
                for j, option in enumerate(q.get('options', [])):
                    if option is None:
                        option = "Option text not available"
                    option_letter = chr(65 + j)  # A, B, C, D...
                    option_text = f"{option_letter}. {option}"
                    wrapped_option = textwrap.fill(option_text, width=80)
                    for line in wrapped_option.split('\n'):
                        pdf.cell(0, 8, line, 0, 1)
                    pdf.ln(1)
            
            # Add answer section if requested
            if include_answers:
                pdf.ln(2)
                pdf.set_font("Arial", "B", 10)
                pdf.cell(0, 8, "Answer:", 0, 1)
                pdf.set_font("Arial", "", 10)
                
                # Get answer and ensure it's not None
                answer_text = q.get('correct_answer', '')
                if answer_text is None:
                    answer_text = "Answer not available"
                    
                # Convert to string if it's not already
                if not isinstance(answer_text, str):
                    answer_text = str(answer_text)
                
                wrapped_answer = textwrap.fill(answer_text, width=85)
                for line in wrapped_answer.split('\n'):
                    pdf.cell(0, 8, line, 0, 1)
                
                if 'explanation' in q and q.get('explanation'):
                    pdf.ln(2)
                    pdf.set_font("Arial", "I", 10)
                    pdf.cell(0, 8, "Explanation:", 0, 1)
                    
                    # Get explanation and ensure it's not None
                    explanation_text = q.get('explanation', '')
                    if explanation_text is None:
                        explanation_text = "Explanation not available"
                        
                    # Convert to string if it's not already
                    if not isinstance(explanation_text, str):
                        explanation_text = str(explanation_text)
                    
                    wrapped_explanation = textwrap.fill(explanation_text, width=85)
                    for line in wrapped_explanation.split('\n'):
                        pdf.cell(0, 8, line, 0, 1)
            
            pdf.ln(5)
        
        # Save to a temporary file
        output_path = f"/tmp/temp_outputs/exam_{str(uuid.uuid4())[:8]}.pdf"
        pdf.output(output_path)
        return output_path
        
    except Exception as e:
        print(f"PDF generation error: {str(e)}")
        # Create a simple error PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Error Generating PDF", 0, 1, "C")
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, "An error occurred while generating the PDF.", 0, 1)
        pdf.cell(0, 10, f"Error: {str(e)}", 0, 1)
        
        error_path = f"/tmp/temp_outputs/error_{str(uuid.uuid4())[:8]}.pdf"
        pdf.output(error_path)
        return error_path

def generate_html(questions, exam_title, include_answers=False):
    """Generate an HTML file with the questions."""
    try:
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{exam_title}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ text-align: center; }}
                h2 {{ margin-top: 20px; color: #2c3e50; }}
                h3 {{ color: #3498db; }}
                .question {{ margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .difficulty {{ font-size: 0.9em; color: #7f8c8d; }}
                .options {{ margin-left: 20px; }}
                .answer {{ margin-top: 10px; padding: 10px; background-color: #f8f9fa; display: {'' if include_answers else 'none'}; }}
                .explanation {{ font-style: italic; margin-top: 5px; }}
            </style>
        </head>
        <body>
            <h1>{exam_title}</h1>
            <p style="text-align: right;">Date: {datetime.now().strftime('%Y-%m-%d')}</p>
        """
        
        current_topic = None
        current_type = None
        
        for i, q in enumerate(questions):
            # Skip any invalid question
            if not isinstance(q, dict):
                continue
                
            # Safety check to ensure q is a dictionary with required fields
            q_text = q.get('text', 'Question text missing')
            q_topic = q.get('topic', 'General')
            q_type = q.get('type', 'General')
            q_difficulty = q.get('difficulty', 'Medium')
            
            # Add topic header if it changes
            if q_topic != current_topic:
                current_topic = q_topic
                html += f"<h2>Topic: {current_topic}</h2>"
            
            # Add question type header if it changes
            if q_type != current_type:
                current_type = q_type
                html += f"<h3>Section: {current_type} Questions</h3>"
            
            # Add question
            html += f"""
            <div class="question">
                <p><strong>Question {i+1}</strong> <span class="difficulty">({q_difficulty} Difficulty)</span></p>
                <p>{q_text}</p>
            """
            
            # Add options for MCQs
            if q_type == 'MCQ' and 'options' in q and isinstance(q.get('options'), list):
                html += '<div class="options">'
                for j, option in enumerate(q.get('options', [])):
                    if option is None:
                        option = "Option text not available"
                    option_letter = chr(65 + j)  # A, B, C, D...
                    html += f"<p>{option_letter}. {option}</p>"
                html += '</div>'
            
            # Add answer section
            answer_text = q.get('correct_answer', '')
            if answer_text is None:
                answer_text = "Answer not available"
                
            explanation_text = q.get('explanation', '')
            if explanation_text is None:
                explanation_text = "Explanation not available"
                
            html += f"""
                <div class="answer">
                    <p><strong>Answer:</strong> {answer_text}</p>
            """
            
            if explanation_text:
                html += f'<p class="explanation"><strong>Explanation:</strong> {explanation_text}</p>'
            
            html += """
                </div>
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        
        # Save to a temporary file
        output_path = f"/tmp/temp_outputs/exam_{str(uuid.uuid4())[:8]}.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        return output_path
        
    except Exception as e:
        print(f"HTML generation error: {str(e)}")
        # Create a simple error HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error</title>
        </head>
        <body>
            <h1>Error Generating HTML</h1>
            <p>An error occurred while generating the HTML document.</p>
            <p>Error: {str(e)}</p>
        </body>
        </html>
        """
        
        error_path = f"/tmp/temp_outputs/error_{str(uuid.uuid4())[:8]}.html"
        with open(error_path, 'w', encoding='utf-8') as f:
            f.write(html)
        return error_path

def generate_markdown(questions, exam_title, include_answers=False):
    """Generate a Markdown file with the questions."""
    try:
        md = f"# {exam_title}\n\nDate: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        
        current_topic = None
        current_type = None
        
        for i, q in enumerate(questions):
            # Skip any invalid question
            if not isinstance(q, dict):
                continue
                
            # Safety check to ensure q is a dictionary with required fields
            q_text = q.get('text', 'Question text missing')
            q_topic = q.get('topic', 'General')
            q_type = q.get('type', 'General')
            q_difficulty = q.get('difficulty', 'Medium')
            
            # Add topic header if it changes
            if q_topic != current_topic:
                current_topic = q_topic
                md += f"## Topic: {current_topic}\n\n"
            
            # Add question type header if it changes
            if q_type != current_type:
                current_type = q_type
                md += f"### Section: {current_type} Questions\n\n"
            
            # Add question
            md += f"**Question {i+1}** ({q_difficulty} Difficulty)\n\n{q_text}\n\n"
            
            # Add options for MCQs
            if q_type == 'MCQ' and 'options' in q and isinstance(q.get('options'), list):
                for j, option in enumerate(q.get('options', [])):
                    if option is None:
                        option = "Option text not available"
                    option_letter = chr(65 + j)  # A, B, C, D...
                    md += f"{option_letter}. {option}\n\n"
            
            # Add answer section if requested
            if include_answers:
                answer_text = q.get('correct_answer', '')
                if answer_text is None:
                    answer_text = "Answer not available"
                    
                md += f"**Answer:** {answer_text}\n\n"
                
                explanation_text = q.get('explanation', '')
                if explanation_text is not None and explanation_text:
                    md += f"*Explanation:* {explanation_text}\n\n"
            
            md += "---\n\n"
        
        # Save to a temporary file
        output_path = f"/tmp/temp_outputs/exam_{str(uuid.uuid4())[:8]}.md"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md)
        return output_path
        
    except Exception as e:
        print(f"Markdown generation error: {str(e)}")
        # Create a simple error markdown
        md = f"# Error Generating Markdown\n\nAn error occurred while generating the markdown document.\n\nError: {str(e)}\n"
        
        error_path = f"/tmp/temp_outputs/error_{str(uuid.uuid4())[:8]}.md"
        with open(error_path, 'w', encoding='utf-8') as f:
            f.write(md)
        return error_path

# --- API Routes ---
@app.route('/api/health')
def health_check():
    return jsonify({"status": "healthy", "service": "Question Paper Gen API"})

@app.route('/api/models', methods=['GET'])
def get_models():
    try:
        models = [m for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        model_list = [{"name": m.name, "displayName": getattr(m, 'display_name', m.name), "version": getattr(m, 'version', 'unknown')} for m in models]
        return jsonify({"models": model_list})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    # Retrieve form data
    subject_name = request.form.get('subject', 'General Subject')
    subject_details = request.form.get('subject_details', '')
    file_uri = request.form.get('file_uri')
    mime_type = request.form.get('mime_type')
    filename_str = request.form.get('filename')

    filepath = None
    fallback_text = None

    # Determine if we received a direct upload URI or we need to process a file payload
    if file_uri:
         # Best Case: Direct Browser Upload bypass limit
         print(f"Received proxy file_uri from frontend: {file_uri}")
    elif 'file' in request.files and request.files['file'].filename != '':
        # Fallback Case: Standard multipart/form-data payload
        file = request.files['file']
        
        filename_str = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename_str)
        file.save(filepath)
        
        # Upload the file directly to Gemini to get a URI (replaces local PyPDF logic)
        file_uri = process_file_to_gemini(filepath, display_name=filename_str)
        
        if not file_uri:
             # If upload fails for some reason, fall back to simple text
             if filepath.endswith('.txt') or filepath.endswith('.md'):
                 with open(filepath, 'r', encoding='utf-8') as f:
                     fallback_text = f.read()
             else:
                 return jsonify({"error": "Failed to proxy file to Gemini API constraints."}), 500
    else:
        print("No file provided. Generating based on subject only.")
    
    # Analyze content
    analysis_result = analyze_content(file_uri, subject_name, fallback_text=fallback_text, subject_details=subject_details)
    
    if not analysis_result['success']:
        status_code = 429 if '429' in str(analysis_result.get('error', '')) or 'quota' in str(analysis_result.get('error', '')).lower() else 500
        return jsonify(analysis_result), status_code
    
    return jsonify({
        "success": True,
        "filename": filename_str,
        "file_uri": file_uri,
        "mime_type": mime_type,
        "topics": analysis_result.get('topics', []),
        "content_preview": "Content analyzed securely via Gemini API. Native text preview suppressed for security."
    })

@app.route('/api/generate-questions', methods=['POST'])
def generate_questions_api():
    req_json = request.json
    try:
        # Since we modified the frontend to send file_uri instead of relying purely on filename,
        # we bypass Pydantic static validation briefly if it fails
        data = GenerateQuestionsRequest(**req_json)
    except ValidationError as e:
        print(f"Validation Error: {e}")
        # Proceed with raw json data for URI forwarding
        data = type('obj', (object,), req_json)()
    
    filename = getattr(data, 'filename', 'unknown_file')
    file_uri = req_json.get('file_uri')
    
    question_bank = getattr(data, 'question_bank', [])
    
    params = {
        'subject': getattr(data, 'subject', 'General'),
        'subject_details': getattr(data, 'subject_details', req_json.get('subject_details', '')),
        'topics': getattr(data, 'topics', []),
        'difficulty': getattr(data, 'difficulty', 'Medium'),
        'question_types': getattr(data, 'question_types', ['MCQ']),
        'num_questions': int(getattr(data, 'num_questions', 10))
    }
    
    num_from_bank = min(int(params['num_questions'] / 2), len(question_bank))
    num_to_generate = params['num_questions'] - num_from_bank
    
    # Generate Questions
    fallback_text = None
    if not file_uri:
         # Fallback to older logic if no URI is present
         filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
         if os.path.exists(filepath):
             if filepath.endswith('.txt') or filepath.endswith('.md'):
                 with open(filepath, 'r', encoding='utf-8') as f:
                     fallback_text = f.read()

    gen_result = {"questions": []} if num_to_generate <= 0 else generate_questions(file_uri, {**params, 'num_questions': num_to_generate}, fallback_text=fallback_text)
    
    if not gen_result.get('success', False) and num_to_generate > 0:
        status_code = 429 if '429' in str(gen_result.get('error', '')) or 'quota' in str(gen_result.get('error', '')).lower() else 500
        return jsonify(gen_result), status_code
    
    # Select questions from bank
    selected_questions = [] if num_from_bank <= 0 else select_questions_from_bank(question_bank, {**params, 'num_questions': num_from_bank})
    
    # Combine questions
    all_questions = combine_questions(
        gen_result.get('questions', []), 
        selected_questions, 
        params['num_questions']
    )
    
    return jsonify({
        "success": True,
        "questions": all_questions
    })

@app.route('/api/export', methods=['POST'])
def export_paper():
    try:
        try:
            req_data = ExportPaperRequest(**(request.json if request.is_json else request.form))
        except ValidationError as e:
            return jsonify({"error": "Invalid request payload", "details": e.errors()}), 400
        
        questions = req_data.questions
        if isinstance(questions, str):
            questions = json.loads(questions)
            
        if not questions:
            return jsonify({"error": "No questions provided"}), 400
        
        format_type = req_data.format
        exam_title = req_data.title
        include_answers = str(req_data.include_answers).lower() == 'true' if isinstance(req_data.include_answers, str) else req_data.include_answers

        
        if format_type == 'pdf':
            output_path = generate_pdf(questions, exam_title, include_answers)
            mime_type = 'application/pdf'
        elif format_type == 'html':
            output_path = generate_html(questions, exam_title, include_answers)
            mime_type = 'text/html'
        elif format_type == 'md':
            output_path = generate_markdown(questions, exam_title, include_answers)
            mime_type = 'text/markdown'
        else:
            return jsonify({"error": f"Unsupported format: {format_type}"}), 400
        
        # Return file for download
        return send_file(
            output_path,
            as_attachment=True,
            download_name=f"{exam_title.replace(' ', '_')}_{format_type}.{format_type}",
            mimetype=mime_type
        )
    except Exception as e:
        print(f"Error in export: {str(e)}")
        return jsonify({"error": f"Failed to generate {format_type}: {str(e)}"}), 500

@app.route('/api/convert-html-to-pdf', methods=['POST'])
def convert_html_to_pdf():
    try:
        req_data = ConvertHtmlRequest(**request.json)
    except ValidationError as e:
        return jsonify({"error": "Invalid request payload", "details": e.errors()}), 400

    html_content = req_data.html
    
    try:
        # Save HTML to temporary file
        html_path = f"/tmp/temp_outputs/temp_{str(uuid.uuid4())[:8]}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Convert to PDF
        pdf_path = f"/tmp/temp_outputs/exam_{str(uuid.uuid4())[:8]}.pdf"
        pdfkit.from_file(html_path, pdf_path)
        
        # Clean up HTML file
        os.remove(html_path)
        
        # Return file for download
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"exam_paper.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        return jsonify({"error": f"Failed to convert HTML to PDF: {str(e)}"}), 500

# --- Error Handlers ---
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": "File too large"}), 413

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": "Bad request"}), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Unhandled exception: {str(e)}")
    return jsonify({"error": "An unexpected error occurred"}), 500

# Create necessary directories and files if they don't exist
def ensure_directories():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('/tmp/temp_outputs', exist_ok=True)

@app.before_request
def configure_gemini_for_request():
    if request.path.startswith('/api/'):
        custom_key = request.headers.get('X-Gemini-Api-Key')
        if custom_key:
            genai.configure(api_key=custom_key)
        else:
            default_key = os.environ.get("GOOGLE_API_KEY", "***REDACTED_API_KEY***")
            if default_key:
                genai.configure(api_key=default_key)
        
        custom_model = request.headers.get('X-Gemini-Model-Name')
        g.gemini_model_name = custom_model if custom_model else model.model_name

# --- Main Entry Point ---
if __name__ == '__main__':
    ensure_directories()
    print(f"Upload folder: {os.path.abspath(app.config['UPLOAD_FOLDER'])}")
    app.run(debug=True)