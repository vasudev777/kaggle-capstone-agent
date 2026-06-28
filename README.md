# ⚡ Smart Planner & Task Concierge Agent (Kaggle Capstone Project)

This project is a premium AI-driven personal tutor and productivity workspace built as a Capstone Project for the **Kaggle 5-Day AI Agents Intensive Course**. It implements a dual-agent orchestrator with dynamic resource lookup, state storage memory, and a gorgeous glassmorphic web interface.

---

## 🌟 Key Course Concepts Demonstrated

This project satisfies **three core agentic concepts** required for the Kaggle Capstone:

1. **Multi-Agent Architecture (ADK Style):**
   - **Planner Agent:** Formats goals, plans structures, schedules day-by-day tasks, and uses structured Pydantic schemas to validate output.
   - **Task Manager Agent (Coach):** Handles live interactions, offers instructions for specific tasks, and responds in-context of the task board.

2. **MCP-style Tools & Skills:**
   - `load_workspace_state()`: Reads current state and chat history.
   - `save_workspace_state()`: Writes updated status and goals to JSON.
   - `generate_resource_links()`: A dynamic skill that looks up and injects learning resources (videos/docs) into task cards.

3. **Memory & State Management:**
   - Persistent memory is maintained in a local `workspace_state.json` file. The agent retains context across server restarts and records progress transitions.

---

## 🛠️ Tech Stack
- **Backend:** FastAPI (Python), Uvicorn Server, `google-generativeai` SDK
- **AI Model:** `gemini-2.5-flash`
- **Frontend:** Glassmorphic Dark UI (Vanilla HTML5, CSS3, ES6 JavaScript)
- **Database:** Local JSON File State (persistent memory)

---

## 🚀 Setup & Installation Instructions

Follow these simple steps to run the project locally on your system:

### Step 1: Open Your Terminal
Open PowerShell, CMD, or Git Bash in this project directory:
```bash
D:\New Skills\agentic AI\Smart Planner & Task Concierge Agent
```

### Step 2: Install Python Dependencies
Install the required packages using pip:
```bash
pip install -r requirements.txt
```

### Step 3: Run the FastAPI Server
Launch the development server:
```bash
uvicorn main:app --reload
```
You will see output indicating that the server is running on `http://127.0.0.1:8000`.

### Step 4: Open the App in Your Browser
Open your browser and navigate to:
```
http://127.0.0.1:8000/
```

### Step 5: Input Gemini API Key & Set Goal
1. Click the **"Key Setup"** button in the top right.
2. Enter your **Google Gemini API Key** and click "Save". (This will create a `.env` file containing `GEMINI_API_KEY=your_key` in the folder).
3. Under **"Start A New Roadmap"**, type a goal (e.g. *"Learn Pandas for data analysis in 3 days"*).
4. Select the duration and click **"Generate Agentic Plan"**.
5. Let the AI Planner Agent build your board, and start working with your interactive dashboard!

---
*Created for the Kaggle 5-Day AI Agents Capstone Project.*
