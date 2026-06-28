import os
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from typing import Dict, Any, Optional

from fpdf import FPDF
from collections import defaultdict
from agent import AgentOrchestrator, load_workspace_state, save_workspace_state

app = FastAPI(title="Smart Planner & Task Concierge Agent API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)

orchestrator = AgentOrchestrator()

class KeyPayload(BaseModel):
    api_key: str

class GoalPayload(BaseModel):
    goal: str
    duration_days: int

class ChatPayload(BaseModel):
    message: str

class TaskUpdatePayload(BaseModel):
    task_id: str
    status: str

@app.get("/api/status")
def get_status():
    """Check if the Gemini API Key is configured."""
    return {
        "status": "running",
        "has_api_key": orchestrator.is_configured(),
        "state_initialized": bool(load_workspace_state().get("goal"))
    }

@app.post("/api/set_key")
def set_key(payload: KeyPayload):
    """Dynamically configure the Gemini API Key from the UI."""
    if not payload.api_key.strip():
        raise HTTPException(status_code=400, detail="API Key cannot be empty")
    
    orchestrator.set_api_key(payload.api_key.strip())
    # Save key to .env for persistence in workspace folder
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(f"GEMINI_API_KEY={payload.api_key.strip()}\n")
        
    return {"message": "Gemini API Key configured successfully and saved to local environment."}

@app.get("/api/workspace")
def get_workspace():
    """Retrieve the current workspace state."""
    return load_workspace_state()

@app.post("/api/init_goal")
def init_goal(payload: GoalPayload):
    """Trigger the Planner Agent to generate tasks for the user's goal."""
    if not orchestrator.is_configured():
        raise HTTPException(status_code=400, detail="Gemini API Key is not set. Please set it first.")
    
    if not payload.goal.strip() or payload.duration_days <= 0:
        raise HTTPException(status_code=400, detail="Invalid goal or duration.")

    try:
        # 1. Generate new structured plan via Planner Agent
        plan = orchestrator.generate_plan(payload.goal, payload.duration_days)
        
        # 2. Setup fresh state with the plan
        state = load_workspace_state()
        state["goal"] = plan["goal"]
        state["duration_days"] = plan["duration_days"]
        state["tasks"] = plan["tasks"]
        
        # 3. Add system welcome message
        welcome_text = (
            f"I have successfully created a {payload.duration_days}-day plan for your goal: "
            f"**\"{plan['goal']}\"**! I've loaded {len(plan['tasks'])} tasks onto your dashboard with curated resources. "
            "How would you like to start? Let me know if you need help with any specific day's work."
        )
        state["chat_history"].append({
            "sender": "agent",
            "text": welcome_text
        })
        
        save_workspace_state(state)
        return state
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate plan: {str(e)}")

@app.post("/api/chat")
def chat_with_agent(payload: ChatPayload):
    """Chat with the Coach Agent in-context of the task board."""
    if not orchestrator.is_configured():
        raise HTTPException(status_code=400, detail="Gemini API Key is not set.")
    
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # 1. Load state and record user message
    state = load_workspace_state()
    state["chat_history"].append({
        "sender": "user",
        "text": payload.message
    })
    
    try:
        # 2. Run Coach Agent response
        reply = orchestrator.chat_agent(payload.message)
        
        # 3. Record agent reply and save
        state["chat_history"].append({
            "sender": "agent",
            "text": reply
        })
        save_workspace_state(state)
        return {"reply": reply, "chat_history": state["chat_history"]}
    except Exception as e:
        # Revert message if failed
        state["chat_history"].pop()
        raise HTTPException(status_code=500, detail=f"Agent Error: {str(e)}")

@app.post("/api/update_task")
def update_task_status(payload: TaskUpdatePayload):
    """Update status of a specific task."""
    state = load_workspace_state()
    task_found = False
    
    for task in state.get("tasks", []):
        if task["id"] == payload.task_id:
            old_status = task["status"]
            task["status"] = payload.status
            task_found = True
            
            # Log transition to agent chat history dynamically (Contextual awareness)
            log_msg = f"[System Alert] Task '{task['title']}' updated from {old_status.upper()} to {payload.status.upper()}."
            state["chat_history"].append({
                "sender": "agent",
                "text": log_msg
            })
            break
            
    if not task_found:
        raise HTTPException(status_code=404, detail="Task not found")
        
    save_workspace_state(state)
    return state

@app.post("/api/reset")
def reset_workspace():
    """Reset the workspace state back to default initial state."""
    state = {
        "goal": "",
        "duration_days": 0,
        "tasks": [],
        "chat_history": [
            {
                "sender": "agent",
                "text": "Hello! I am your AI Workspace Concierge. What is your goal or learning path? For example, tell me: 'I want to learn HTML & CSS basics in 3 days' or 'Build a basic FastAPI application in 2 days'!"
            }
        ]
    }
    save_workspace_state(state)
    return state


@app.get("/api/export")
def export_plan():
    """Export the current workspace learning plan and progress as a beautiful Markdown report."""
    state = load_workspace_state()
    if not state.get("goal"):
        raise HTTPException(status_code=400, detail="No active goal to export.")

    # Calculate statistics
    tasks = state.get("tasks", [])
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t["status"] == "completed")
    in_progress_tasks = sum(1 for t in tasks if t["status"] == "in_progress")
    todo_tasks = sum(1 for t in tasks if t["status"] == "todo")
    percent = int((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0

    md_content = f"""# 🎯 Goal Workspace Report: {state['goal']}

This workspace report was generated by the **Smart Workspace & Task Concierge Agent**.

## 📊 Progress Summary
- **Overall Goal:** {state['goal']}
- **Project Duration:** {state['duration_days']} Days
- **Completion Rate:** {percent}% ({completed_tasks}/{total_tasks} Tasks completed)
- **Status Breakdown:**
  - 📝 To-Do: {todo_tasks}
  - 🔄 In Progress: {in_progress_tasks}
  - ✅ Completed: {completed_tasks}

---

## 📅 Day-by-Day Learning Roadmap
"""
    # Group tasks by day
    from collections import defaultdict
    tasks_by_day = defaultdict(list)
    for task in tasks:
        tasks_by_day[task["day"]].append(task)

    for day in sorted(tasks_by_day.keys()):
        md_content += f"\n### 📆 Day {day}\n"
        for t in tasks_by_day[day]:
            status_emoji = "✅" if t["status"] == "completed" else ("🔄" if t["status"] == "in_progress" else "📝")
            md_content += f"- **[{status_emoji}] {t['title']}** (ID: `{t['id']}`)\n"
            md_content += f"  - *Description:* {t['description']}\n"
            if t.get("resources"):
                md_content += "  - *Resources:*\n"
                for res in t["resources"]:
                    res_type = "🎥 Video" if res["type"] == "video" else "📖 Article"
                    md_content += f"    - [{res_type}] {res['title']} ({res['url']})\n"

    md_content += """
---
*Generated with ❤️ by your Kaggle Capstone AI Workspace Agent. Good luck on your path!*
"""

    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=learning_plan_report.md"}
    )

@app.get("/api/export_pdf")
def export_pdf():
    """Export the workspace goal roadmap as a clean PDF download."""
    state = load_workspace_state()
    if not state.get("goal"):
        raise HTTPException(status_code=400, detail="No active goal to export.")

    tasks = state.get("tasks", [])
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t["status"] == "completed")
    in_progress_tasks = sum(1 for t in tasks if t["status"] == "in_progress")
    todo_tasks = sum(1 for t in tasks if t["status"] == "todo")
    percent = int((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0

    class PDF(FPDF):
        def header(self):
            self.set_font('helvetica', 'B', 15)
            self.cell(0, 10, 'Goal Roadmap & Workspace Report', border=False, ln=True, align='C')
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('helvetica', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', align='C')

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Title / Metadata
    pdf.set_font("helvetica", "B", 14)
    # Clean goal string from any emojis if present (we can encode/decode ignore or replace)
    clean_goal = state['goal'].encode('ascii', 'ignore').decode('ascii')
    pdf.cell(0, 10, f"Goal: {clean_goal}", ln=True)
    pdf.set_font("helvetica", "", 12)
    pdf.cell(0, 8, f"Duration: {state['duration_days']} Days", ln=True)
    pdf.cell(0, 8, f"Progress: {percent}% ({completed_tasks}/{total_tasks} completed)", ln=True)
    pdf.cell(0, 8, f"Breakdown: TODO: {todo_tasks} | In Progress: {in_progress_tasks} | Completed: {completed_tasks}", ln=True)
    pdf.ln(8)

    # Group tasks by day
    tasks_by_day = defaultdict(list)
    for task in tasks:
        tasks_by_day[task["day"]].append(task)

    for day in sorted(tasks_by_day.keys()):
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 8, f"Day {day}", ln=True)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        
        for t in tasks_by_day[day]:
            status_symbol = "[DONE]" if t["status"] == "completed" else ("[WORKING]" if t["status"] == "in_progress" else "[TODO]")
            clean_title = t['title'].encode('ascii', 'ignore').decode('ascii')
            pdf.set_font("helvetica", "B", 10)
            pdf.cell(0, 6, f"{status_symbol} {clean_title}", ln=True)
            
            clean_desc = t['description'].encode('ascii', 'ignore').decode('ascii')
            pdf.set_font("helvetica", "", 10)
            pdf.multi_cell(pdf.epw, 5, f"Description: {clean_desc}")
            
            if t.get("resources"):
                pdf.set_font("helvetica", "I", 9)
                res_list = []
                for res in t["resources"]:
                    res_title = res['title'].encode('ascii', 'ignore').decode('ascii')
                    res_list.append(f"{res_title}: {res['url']}")
                resources_str = "Resources: " + " | ".join(res_list)
                pdf.multi_cell(pdf.epw, 5, resources_str)
                
            pdf.ln(4)
            
    # Output PDF to bytes
    pdf_bytes = pdf.output()
    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=learning_plan_report.pdf"}
    )


# Serve Frontend SPA files
@app.get("/")
def serve_index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))

@app.get("/styles.css")
def serve_css():
    return FileResponse(os.path.join(os.path.dirname(__file__), "styles.css"))

@app.get("/app.js")
def serve_js():
    return FileResponse(os.path.join(os.path.dirname(__file__), "app.js"))
