import os
import json
import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import google.generativeai as genai
from dotenv import load_dotenv

# Load local environment variables from .env
load_dotenv()

STATE_FILE = os.path.join(os.path.dirname(__file__), "workspace_state.json")

# Define Data Models for Structured Outputs
class Resource(BaseModel):
    title: str = Field(description="The name of the resource, e.g., 'MDN Web Docs - Flexbox'")
    url: str = Field(description="A direct URL link to the resource, or a search engine link if specific is unknown")
    type: str = Field(description="Type of resource: 'article' or 'video'")

class TaskItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()[:8]), description="A unique short ID for the task")
    title: str = Field(description="A concise title of the task")
    description: str = Field(description="Details on what the user needs to build or learn")
    day: int = Field(description="The relative day number this task is scheduled for (e.g., 1, 2, 3)")
    status: str = Field(default="todo", description="Status of the task. Must be 'todo'")
    resources: List[Resource] = Field(default=[], description="List of 2-3 high-quality learning resources for this specific task")

class LearningPlan(BaseModel):
    goal: str = Field(description="The cleaned up overarching goal description")
    duration_days: int = Field(description="The duration in days for the plan")
    tasks: List[TaskItem] = Field(description="The full list of tasks divided across the days")

# Core Tools (MCP-style skills)
def load_workspace_state() -> Dict[str, Any]:
    """MCP Tool: Load the current workspace state/memory from the JSON file."""
    if not os.path.exists(STATE_FILE):
        return {"goal": "", "duration_days": 0, "tasks": [], "chat_history": []}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"goal": "", "duration_days": 0, "tasks": [], "chat_history": []}

def save_workspace_state(state: Dict[str, Any]) -> None:
    """MCP Tool: Save the current workspace state/memory to the JSON file."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def generate_resource_links(topic: str) -> List[Dict[str, str]]:
    """MCP Tool Skill: Generate high-quality mock search/resource links for standard web/coding topics."""
    topic_lower = topic.lower()
    resources = []
    
    # Custom resource mappings based on topics
    if "python" in topic_lower:
        resources = [
            {"title": "W3Schools Python Tutorial", "url": "https://www.w3schools.com/python/", "type": "article"},
            {"title": "Python for Beginners (YouTube)", "url": "https://www.youtube.com/watch?v=kqtD5dpnC8U", "type": "video"},
            {"title": "Python Official Documentation", "url": "https://docs.python.org/3/", "type": "article"}
        ]
    elif "react" in topic_lower:
        resources = [
            {"title": "React Official Docs", "url": "https://react.dev/", "type": "article"},
            {"title": "React JS Full Course (YouTube)", "url": "https://www.youtube.com/watch?v=Ke90Tje7VS0", "type": "video"}
        ]
    elif "html" in topic_lower or "css" in topic_lower:
        resources = [
            {"title": "MDN Web Docs - HTML & CSS basics", "url": "https://developer.mozilla.org/en-US/docs/Learn/Getting_started_with_the_web/HTML_basics", "type": "article"},
            {"title": "HTML & CSS Full Course (YouTube)", "url": "https://www.youtube.com/watch?v=mU6anWqZJcc", "type": "video"}
        ]
    elif "fastapi" in topic_lower:
        resources = [
            {"title": "FastAPI Tutorial - User Guide", "url": "https://fastapi.tiangolo.com/tutorial/", "type": "article"},
            {"title": "FastAPI Course for Beginners (YouTube)", "url": "https://www.youtube.com/watch?v=tLKKmCOH_t0", "type": "video"}
        ]
    else:
        # Fallback to search query links
        search_query = topic.replace(" ", "+")
        resources = [
            {"title": f"Search Google for {topic}", "url": f"https://www.google.com/search?q={search_query}", "type": "article"},
            {"title": f"Search YouTube for {topic}", "url": f"https://www.youtube.com/results?search_query={search_query}", "type": "video"}
        ]
    return resources[:3]

class AgentOrchestrator:
    def __init__(self):
        # Configure the Gemini API key
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        if self.api_key:
            genai.configure(api_key=self.api_key)
        self.model_name = "gemini-2.5-flash"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def set_api_key(self, api_key: str):
        self.api_key = api_key
        genai.configure(api_key=api_key)

    def generate_plan(self, goal: str, duration_days: int) -> Dict[str, Any]:
        """
        Agent A: Planner Agent
        Takes a goal and duration, designs a structured learning path with tasks, 
        and adds learning resources using tool calling.
        """
        if not self.is_configured():
            raise ValueError("Gemini API Key is not set. Please set it in the settings or .env file.")

        planner_system_prompt = (
            "You are the Lead Planning Architect Agent. Your role is to take a user's high-level learning "
            "or project goal and break it down into a highly structured day-by-day plan. "
            "For each day, specify exactly 1 to 3 distinct tasks that must be done. "
            "For each task, provide clear descriptions and high-quality learning resources (YouTube videos or official docs)."
        )

        prompt = f"Goal: {goal}\nDuration: {duration_days} Days.\nPlease create a complete learning plan."

        # Call Gemini with structured output validation
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=planner_system_prompt
        )

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=LearningPlan,
                temperature=0.2
            )
        )

        plan_data = json.loads(response.text)
        
        # Post-process to ensure IDs and Resources are set nicely if Gemini didn't fill them completely
        for task in plan_data.get("tasks", []):
            if "id" not in task or not task["id"]:
                task["id"] = str(uuid.uuid4()[:8])
            task["status"] = "todo"
            # Use our resource skill if the agent didn't provide good links
            if not task.get("resources"):
                task["resources"] = generate_resource_links(task["title"])

        return plan_data

    def chat_agent(self, user_message: str) -> str:
        """
        Agent B: Task Manager / Interactive Coach
        Handles conversation, knows about the current workspace tasks and status,
        and provides guidance on how to accomplish tasks.
        """
        if not self.is_configured():
            raise ValueError("Gemini API Key is not set.")

        state = load_workspace_state()
        tasks_summary = json.dumps(state.get("tasks", []), indent=2)
        goal = state.get("goal", "None set yet")
        duration = state.get("duration_days", 0)

        coach_system_prompt = (
            "You are the Interactive Workspace Concierge & Coding Coach. Your role is to help the user "
            "with their current tasks, answer coding questions, provide tips, and keep them motivated. "
            "You know their current goal and task board.\n\n"
            f"Current Goal: {goal} ({duration} days)\n"
            f"Task Board State:\n{tasks_summary}\n\n"
            "Guidelines:\n"
            "1. Be friendly, encouraging, and clear.\n"
            "2. If the user asks about a specific task, explain it and give a code sample or direct tip.\n"
            "3. If they ask about their progress, summarize what's done, in progress, and todo.\n"
            "4. Keep answers concise, and format code snippets in markdown."
        )

        # Assemble chat history for context
        history = []
        for msg in state.get("chat_history", [])[-10:]: # Keep last 10 messages for context
            history.append({
                "role": "user" if msg["sender"] == "user" else "model",
                "parts": [msg["text"]]
            })

        # Set up Gemini Chat
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=coach_system_prompt
        )

        chat = model.start_chat(history=history[:-1] if history else [])
        
        response = chat.send_message(user_message)
        return response.text
