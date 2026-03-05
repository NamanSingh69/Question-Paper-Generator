#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil

def check_python_version():
    """Check if Python version is 3.8+"""
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required.")
        sys.exit(1)

def check_dependencies():
    """Check if dependencies are installed"""
    try:
        import pip
    except ImportError:
        print("Error: pip is not installed.")
        sys.exit(1)
    
    # Create requirements.txt if it doesn't exist
    if not os.path.exists('requirements.txt'):
        with open('requirements.txt', 'w') as f:
            f.write("""flask==2.3.3
google-generativeai==0.3.1
Werkzeug==2.3.7
requests==2.31.0
pdf2image==1.16.3
pytesseract==0.3.10
PyPDF2==3.0.1
pandas==2.1.0
fpdf==1.7.2
markdown==3.4.4
pdfkit==1.0.0
beautifulsoup4==4.12.2
""")

def create_directories():
    """Create necessary directories"""
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('temp_outputs', exist_ok=True)
    os.makedirs(os.path.join('static', 'js'), exist_ok=True)

def copy_static_files():
    """Copy or create necessary static files"""
    # Check for main.js
    if os.path.exists('main.js'):
        shutil.copy('main.js', os.path.join('static', 'js', 'main.js'))
        print("Copied main.js to static/js directory")
    else:
        # Create empty main.js file
        with open(os.path.join('static', 'js', 'main.js'), 'w') as f:
            pass
        print("Created empty main.js file in static/js directory")
    
    # Check for index.html
    if os.path.exists('index.html'):
        shutil.copy('index.html', os.path.join('static', 'index.html'))
        print("Copied index.html to static directory")
    else:
        print("Warning: index.html not found. Please place it in the static directory.")

def check_api_key():
    """Check if Google API key is set"""
    if not os.environ.get('GOOGLE_API_KEY'):
        key = input("Enter your Google API key for Gemini: ").strip()
        if key:
            os.environ['GOOGLE_API_KEY'] = key
            print(f"API key set for this session. For permanent use, add it to your environment variables.")
        else:
            print("Warning: No API key provided. The application may not work correctly.")

def install_dependencies():
    """Install dependencies using pip"""
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

def main():
    """Main function"""
    print("Setting up Exam Question Paper Generator...")
    
    # Run checks
    check_python_version()
    check_dependencies()
    
    # Create directories
    create_directories()
    
    # Copy static files
    copy_static_files()
    
    # Install dependencies
    try:
        install_dependencies()
    except subprocess.CalledProcessError:
        print("Error: Failed to install dependencies.")
        sys.exit(1)
    
    # Check API key
    check_api_key()
    
    print("\nSetup complete! You can now run the application:")
    print(f"  {sys.executable} app.py")

if __name__ == "__main__":
    main()