"""
Pytest configuration for app tests
"""
import os
import pytest
import shutil
from unittest.mock import patch

# Import the app and set the template folder before app initialization
@pytest.fixture(autouse=True, scope="session")
def setup_test_environment():
    """Setup test environment with test templates and static files"""
    test_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(test_dir)
    
    # Create test directories
    template_dir = os.path.join(repo_dir, 'test_templates')
    static_dir = os.path.join(repo_dir, 'test_static')
    
    os.makedirs(template_dir, exist_ok=True)
    os.makedirs(static_dir, exist_ok=True)
    
    # Create a test index.html file if it doesn't exist
    test_index = os.path.join(template_dir, 'index.html')
    if not os.path.exists(test_index):
        with open(test_index, 'w') as f:
            f.write('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audio Converter Test</title>
</head>
<body>
    <div class="logo-container">
        <div class="logo">
            <div class="logo-text">AudioConverter</div>
        </div>
    </div>
    <h1>Audio Converter</h1>
    <p class="subtitle">Convert to mono/8kHz/16-bit WAV format</p>
    <!-- Test content -->
</body>
</html>''')
    
    # Copy any existing static files if needed
    src_static = os.path.join(repo_dir, 'static')
    if os.path.exists(src_static):
        for item in os.listdir(src_static):
            src = os.path.join(src_static, item)
            dst = os.path.join(static_dir, item)
            if os.path.isfile(src) and not os.path.exists(dst):
                shutil.copy2(src, dst)
    
    # Create a minimal CSS file if it doesn't exist
    test_css = os.path.join(static_dir, 'style.css')
    if not os.path.exists(test_css):
        with open(test_css, 'w') as f:
            f.write('/* Test CSS file */\n')
    
    # Create a minimal JS file if it doesn't exist
    test_js = os.path.join(static_dir, 'script.js')
    if not os.path.exists(test_js):
        with open(test_js, 'w') as f:
            f.write('/* Test JavaScript file */\n')
    
    # Now we'll override the app config in our test fixtures
    yield