import google.generativeai as genai
import os
import json

key = os.environ.get('GEMINI_API_KEY')
if not key:
    with open('.env', 'r') as f:
        for line in f:
            if line.startswith('GEMINI_API_KEY='):
                key = line.split('=')[1].strip()

genai.configure(api_key=key)

prompt_text = """
    Generate an exam question paper based on the following parameters:
    - Subject: Data Structures
    - Number of Questions: 2
    - Difficulty: Medium
    - Question Types: ['Short Answer', 'Essay']
    - Topics to Cover: ['General']
    
    Make the questions engaging and clear. Ensure they accurately reflect the requested difficulty and topics.
    
    Return the result as a JSON array of objects with the following structure:
    [
        {
            "text": "Question text",
            "options": ["Option A", "Option B", "Option C", "Option D"], // Only for MCQs
            "correct_answer": "Correct answer or option",
            "explanation": "Explanation of the answer",
            "topic": "Topic/subtopic this covers",
            "difficulty": "Easy/Medium/Hard",
            "type": "MCQ/Short Answer/Essay/etc."
        }
    ]
    
    Ensure the response is valid JSON. Generate unique and diverse questions that test different aspects of the subject.
"""

model = genai.GenerativeModel('gemini-3.1-pro-preview')
try:
    print('Generating...')
    response = model.generate_content(prompt_text)
    print(response.text)
except Exception as e:
    print('Err:', e)
