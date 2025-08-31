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
├── web/                    # Frontend web interface
│   ├── index.html         # Main web page
│   └── pcm-worklet.js     # Audio processing
├── docker-compose.yml     # Container orchestration
└── README.md             # This file
```

**Note**: The backend code is developed and hosted on Kaggle. See the [Kaggle Notebook](https://www.kaggle.com/code/klasta/companion) for the complete backend implementation.

## Quick Start

### Backend (Kaggle Notebook)

The backend is implemented and hosted on Kaggle. To use it:

1. **Visit the Kaggle Notebook**: [Companion Backend](https://www.kaggle.com/code/klasta/companion)
2. **Run the notebook** to start the backend server
3. **Get the WebSocket URL** from the ngrok tunnel output
4. **Use the provided URL** in your frontend

### Frontend Setup

1. **Start Web Server**
   ```bash
   cd web
   python -m http.server 5500 --bind 127.0.0.1
   ```

2. **Access Application**
   - Open browser to: `http://127.0.0.1:5500`
   - Update the WebSocket URL to point to your Kaggle backend

### Docker Setup

```bash
docker-compose up -d
```

## Backend Implementation (Kaggle)

The backend is implemented in a Kaggle notebook with the following key components:

### 🔧 **Core Components**
- **GeminiReflector**: AI director that plans conversation strategies
- **HfActor**: Local language model for generating responses
- **DialogueManager**: Orchestrates the conversation flow
- **CognitiveMemory**: Manages conversation history and user facts

### 🚀 **Key Features**
- **Local Model**: Uses Chronos-Hermes-13B for response generation
- **AI Director**: Gemini 2.0 Flash for conversation planning
- **Identity Protection**: Robust guardrails against AI identity probes
- **Relationship Tracking**: Dynamic relationship stages (Stranger → Friend)
- **Memory System**: Episodic and semantic memory management

### 📡 **Deployment**
- **Kaggle Environment**: Runs on Kaggle's GPU infrastructure
- **ngrok Tunnel**: Exposes local server to the internet
- **WebSocket API**: Real-time bidirectional communication

## Configuration

### Personas
Personas are defined in the Kaggle notebook. Each persona includes:
- **Core Identity**: Name, age, essence, backstory
- **Speech Patterns**: Different tones for stranger/friend/close friend
- **Worldview**: Core beliefs and ethical boundaries
- **Inner World**: Secret fears and emotional triggers

### Memory System
- **Short-term**: Recent conversation turns
- **Long-term**: Semantic facts about the user
- **Relationship Tracking**: Dynamic relationship progression

### Guardrails
- **Content Filtering**: Illegal content detection
- **Identity Protection**: Prevents AI identity revelation
- **Style Enforcement**: Prevents repetitive or inappropriate responses

## API Endpoints

### WebSocket (`/ws`)
Real-time bidirectional communication for chat.

**Message Types:**
- `utterance`: Send/receive chat messages
- Connection automatically provides initial greeting

### Health Check
The backend provides health status through the WebSocket connection.

## Development

### Backend Development
1. **Fork the Kaggle notebook**: [Companion Backend](https://www.kaggle.com/code/klasta/companion)
2. **Modify the code** in the notebook
3. **Test changes** by running the notebook
4. **Share your version** or contribute back

### Adding New Personas
1. Edit the `PERSONAS` dictionary in the Kaggle notebook
2. Add new persona definition following the existing structure
3. Include foundational beliefs, speech patterns, and emotional triggers

### Customizing Emotions
- Modify the `DialogueManager` class for emotion handling
- Adjust relationship progression in `_update_relationship_state`
- Update memory management in `CognitiveMemory`

## Troubleshooting

### Common Issues

1. **Kaggle Backend Connection**
   - Ensure the Kaggle notebook is running
   - Check the ngrok tunnel URL is correct
   - Verify WebSocket connection in browser console

2. **Frontend Connection Issues**
   - Update WebSocket URL to match Kaggle backend
   - Check CORS settings for local development
   - Monitor browser console for connection errors

3. **Model Loading**
   - Kaggle provides GPU resources for model loading
   - Check notebook logs for model initialization status
   - Ensure all dependencies are installed in Kaggle environment

### Logs
- Backend logs are displayed in the Kaggle notebook
- Check browser console for frontend errors
- Monitor WebSocket connection status

## Contributing

1. **Fork the Kaggle notebook**: [Companion Backend](https://www.kaggle.com/code/klasta/companion)
2. **Make your changes** in the notebook
3. **Test thoroughly** by running the notebook
4. **Share your improved version** or contribute back to the main notebook

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with FastAPI, WebSockets, and modern web technologies
- Uses Hugging Face transformers for language models
- Emotion classification powered by RoBERTa
- Backend hosted on Kaggle's GPU infrastructure
- ngrok for secure tunnel creation
