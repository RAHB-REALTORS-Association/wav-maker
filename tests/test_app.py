import os
import sys
import pytest
import tempfile
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, convert_audio


@pytest.fixture
def client():
    """Create a test client for the app."""
    app.config['TESTING'] = True
    app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
    app.config['CONVERTED_FOLDER'] = tempfile.mkdtemp()
    
    with app.test_client() as client:
        yield client
    
    # Cleanup temporary directories
    try:
        os.rmdir(app.config['UPLOAD_FOLDER'])
        os.rmdir(app.config['CONVERTED_FOLDER'])
    except:
        pass


def test_index_route(client):
    """Test the index route returns the expected content."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Audio Converter' in response.data
    assert b'Convert to mono/8kHz/16-bit WAV format' in response.data


def test_upload_no_file(client):
    """Test uploading with no file."""
    response = client.post('/upload')
    assert response.status_code == 400
    assert b'No file part' in response.data


def test_upload_empty_filename(client):
    """Test uploading with an empty filename."""
    response = client.post('/upload', data={'audiofile': (b'', '')})
    assert response.status_code == 400
    assert b'No selected file' in response.data


@patch('app.threading.Thread')
def test_upload_success(mock_thread, client):
    """Test successful file upload starts conversion thread."""
    # Create a small dummy audio file
    with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
        temp_file.write(b'dummy audio content')
        temp_file.flush()
        
        with open(temp_file.name, 'rb') as f:
            response = client.post(
                '/upload',
                data={'audiofile': (f, 'test_audio.mp3')}
            )
    
    assert response.status_code == 200
    assert 'task_id' in response.json
    mock_thread.assert_called_once()
    
    # Verify the thread was started with the correct arguments
    args, kwargs = mock_thread.call_args
    assert kwargs.get('target') == convert_audio


def test_status_unknown(client):
    """Test status check for unknown task ID."""
    response = client.get('/status/nonexistent-task-id')
    assert response.status_code == 200
    assert response.json['status'] == 'unknown'


@patch('app.get_file_md5', return_value='dummy_hash')
@patch('app.os.path.exists', return_value=True)
@patch('app.os.path.getsize', return_value=1024)
@patch('app.mediainfo', return_value={'sample_rate': '44100', 'channels': '2', 'bit_depth': '16'})
@patch('app.AudioSegment')
def test_convert_audio(mock_audiosegment, mock_mediainfo, mock_getsize, mock_exists, mock_md5):
    """Test audio conversion function."""
    # Setup mock AudioSegment
    mock_sound = MagicMock()
    mock_sound.channels = 2
    mock_sound.frame_rate = 44100
    mock_sound.sample_width = 2
    mock_audiosegment.from_file.return_value = mock_sound
    
    # For verification
    mock_converted = MagicMock()
    mock_converted.channels = 1
    mock_converted.frame_rate = 8000
    mock_converted.sample_width = 2
    mock_audiosegment.from_file.side_effect = [mock_sound, mock_converted]
    
    # Test convert_audio function
    task_id = 'test-task-id'
    input_path = 'test_input.mp3'
    output_dir = 'test_output_dir'
    
    with patch('app.conversion_status', {}) as mock_status:
        result = convert_audio(input_path, output_dir, task_id)
        
        # Check if conversion status was updated correctly
        assert mock_status[task_id]['status'] == 'complete'
        assert mock_status[task_id]['progress'] == 100
        
        # Check that audio was converted with the correct parameters
        mock_sound.set_channels.assert_called_once_with(1)
        mock_sound.set_frame_rate.assert_called_once_with(8000)
        
        # Check that export was called with the correct parameters
        mock_sound.export.assert_called_once()
        args, kwargs = mock_sound.export.call_args
        assert kwargs['format'] == 'wav'


def test_download_nonexistent(client):
    """Test download for nonexistent file."""
    response = client.get('/download/nonexistent-task-id')
    assert response.status_code == 404
    assert b'File not found or conversion not complete' in response.data