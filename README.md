# AI Companion

An intelligent conversational AI companion with emotional intelligence, memory, and personality customization.

## Features

### 🤖 **Multi-Personality AI**
- **Mia (Adventurous Traveler)**: A 26-year-old travel blogger with a free-spirited personality
- **Customizable Personas**: Easy to add new personalities with unique speech patterns and backgrounds
- **Emotional Intelligence**: Real-time mood tracking and emotional responses
- **Memory System**: Short-term and long-term memory with vector-based retrieval

### 🎭 **Emotional Intelligence**
- **Mood Engine**: Tracks and responds to emotional states
- **Forgiveness Curve**: Natural emotional recovery over time
- **Emotion Classification**: Uses RoBERTa for text emotion analysis
- **Contextual Responses**: Adapts tone based on conversation history

### 💬 **Advanced Dialogue**
- **WebSocket Communication**: Real-time bidirectional chat
- **Speech-to-Text**: Optional microphone input with Whisper
- **Guardrails**: Content filtering and style enforcement
- **Memory Chips**: Automatic memory injection based on conversation triggers

### 🌐 **Web Interface**
- **Modern UI**: Clean, responsive web interface
- **Real-time Chat**: Live conversation with typing indicators
- **Persona Switching**: Change AI personalities on the fly
- **Terminal Logs**: Debug information and system status

## Architecture

```
Companion/
├── backend/                 # FastAPI backend server
│   ├── app/
│   │   ├── main.py         # WebSocket endpoints and routing
│   │   ├── dialogue.py     # Conversation management
│   │   ├── emotion.py      # Mood and emotion processing
│   │   ├── persona.py      # Personality definitions
│   │   ├── memory.py       # Memory system
│   │   ├── guardrails.py   # Content filtering
│   │   └── stt_stream.py   # Speech-to-text processing
│   ├── requirements.txt    # Python dependencies
│   └── README_run.md       # Backend setup instructions
├── web/                    # Frontend web interface
│   ├── index.html         # Main web page
│   └── pcm-worklet.js     # Audio processing
├── docker-compose.yml     # Container orchestration
└── README.md             # This file
```

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js (for web server)
- Docker (optional)

### Backend Setup

1. **Install Dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Environment Variables**
   ```bash
   # Create .env file in backend directory
   MODEL_ID=Austism/chronos-hermes-13b
   GEMINI_API_KEY=your_gemini_api_key_here
   USE_STT=0  # Set to 1 to enable speech-to-text
   ```

3. **Start Backend Server**
   ```bash
   cd backend
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Frontend Setup

1. **Start Web Server**
   ```bash
   cd web
   python -m http.server 5500 --bind 127.0.0.1
   ```

2. **Access Application**
   - Open browser to: `http://127.0.0.1:5500`
   - Backend API: `http://localhost:8000`

### Docker Setup

```bash
docker-compose up -d
```

## Configuration

### Personas
Personas are defined in `backend/app/persona.py`. Each persona includes:
- **Core Identity**: Name, age, essence, backstory
- **Speech Patterns**: Different tones for stranger/friend/close friend
- **Worldview**: Core beliefs and ethical boundaries
- **Inner World**: Secret fears and emotional triggers

### Memory System
- **Short-term**: Recent conversation turns (Redis)
- **Long-term**: Vector-based semantic memory (Qdrant)
- **Memory Chips**: Automatic injection based on conversation triggers

### Guardrails
- **Content Filtering**: Illegal content detection
- **Style Enforcement**: Prevents repetitive or inappropriate responses
- **Length Control**: Configurable response length limits

## API Endpoints

### WebSocket (`/ws`)
Real-time bidirectional communication for chat.

**Message Types:**
- `chat`: Send user message
- `state_update`: Mood and emotional state updates
- `partial_transcript`: Speech-to-text partial results

### Health Check (`/health`)
Returns server status.

### Kill (`/kill`)
Gracefully terminates the server.

## Development

### Adding New Personas
1. Edit `backend/app/persona.py`
2. Add new persona definition following the existing structure
3. Include foundational beliefs, speech patterns, and emotional triggers

### Customizing Emotions
- Modify `backend/app/emotion.py` for emotion classification
- Adjust forgiveness curves in `MoodEngine`
- Update emotion triggers and responses

### Memory Customization
- Configure memory retention in `backend/app/memory.py`
- Adjust vector similarity thresholds
- Modify memory chip triggers

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure all dependencies are installed: `pip install -r requirements.txt`
   - Check Python version compatibility

2. **WebSocket Connection Issues**
   - Verify backend is running on correct port
   - Check CORS settings for local development

3. **Memory/Model Loading**
   - Ensure sufficient RAM for model loading
   - Check model download permissions

### Logs
- Backend logs are displayed in the web terminal
- Check browser console for frontend errors
- Monitor WebSocket connection status

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with FastAPI, WebSockets, and modern web technologies
- Uses Hugging Face transformers for language models
- Emotion classification powered by RoBERTa
- Vector memory system with Qdrant
