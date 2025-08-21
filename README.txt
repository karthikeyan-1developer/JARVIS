@"
Realtime AI Voice Assistant (LiveKit + Google Gemini)

This is a realtime conversational AI agent (called Jarvis) built by Karthikeyan D.
It joins a LiveKit room, listens to users, and replies instantly with Google Gemini 2.0 Flash, using noise cancellation for clear audio.


Features

 LiveKit Realtime Agent with Google Gemini 2.0 Flash
 Natural voice replies with noise cancellation (BVC)
 Custom personality (Jarvis) defined in prompt.py
 Easy setup with .env for API keys


Project Files

 agent.py  > main script (runs the agent)
 prompt.py > custom instructions and response style
 requirements.txt > Python dependencies
 .env.example > template for environment variables
 README.txt > documentation


Setup and Run

1. Clone the repository
   git clone https://github.com/<yourusername>/livekitgeminiagent.git
   cd livekitgeminiagent

2. Create a .env file
   Copy the example file and fill in your own keys.
   On Linux/Mac:  cp .env.example .env
   On Windows:    copy .env.example .env

3. Install dependencies
   pip install r requirements.txt

4. Run the agent
   python agent.py


Requirements

 Python 3.9 or higher
 LiveKit account and API keys
 Google Realtime API key


Credits

Developed by Karthikeyan D
Powered by LiveKit + Google Gemini
"@ | OutFile FilePath README.txt Encoding UTF8
