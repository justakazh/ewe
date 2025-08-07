# 🧠 EWE - Execution Workflow Engine
<img width="1389" height="515" alt="image" src="https://github.com/user-attachments/assets/b05fcec9-36d4-4e72-8e58-74c9521eb449" />

> Execute tasks in a structured workflow — parallel, fast, organized.  
> Designed for automation, recon workflows, and tool orchestration.

---

## 📌 Introduction

Running recon commands, executing tools, and handling tasks manually one by one can be time-consuming, error-prone, and frustrating. That’s why I built EWE (Execution Workflow Engine) — a workflow engine designed to run tasks in parallel, quickly, and in an organized manner using a structured JSON or YAML workflow file. It helps automate repetitive execution flows and orchestrate CLI-based tools efficiently.

---

## 🚀 Features

| Feature | Description |
|--------|-------------|
| **Workflow-Based Execution** | Run tasks based on a structured JSON/YAML workflow, with full support for nested tasks. |
| **Parallel Task Execution** | Execute tasks at the same level concurrently using threading. |
| **Conditional Child Execution** | Child tasks only run when parent tasks complete successfully (configurable with `--ignore-error-task`). |
| **Dynamic Placeholder Support** | Supports placeholders like `{target}`, `{name}`, `{result}`, `{parent_result}`, etc., replaced at runtime. |
| **Real-Time Logging** | Logs every task’s status, stdout, stderr, and PID to a JSON log file in real-time. |
| **Graceful Shutdown** | Clean handling of `SIGINT`/`SIGTERM` (e.g. Ctrl+C), with all running processes safely terminated and logs updated. |
| **Interactive CLI Mode** | Explore and inspect tasks via a live CLI with commands like `show`, `get`, `go`, `back`, etc. |
| **Tree View Monitoring** | Auto-updating tree view that visually displays each task’s status with color coding. |
| **Silent Mode Support** | Run workflows without terminal interaction, suitable for automation, cronjobs, and CI/CD. |
| **JSON/YAML Workflow Support** | Accepts both `.json` and `.yaml` formatted workflow files. |
| **Easy Integration** | Designed to be easily integrated into web apps, dashboards, or your own custom tools via subprocess or system calls. |

---

## 📦 Installation

```bash
git clone https://github.com/justakazh/ewe.git
cd ewe
pip install -r requirements.txt
python3 main.py --help
```

---

## 🧪 Usage

### CLI Options
```bash
Usage: main.py [options]

Options:
  -h, --help              Show help message and exit
  -t, --target            Target value
  -jw, --json-workflow    JSON workflow file
  -yw, --yaml-workflow    YAML workflow file
  -o, --output            Output folder
  -sj, --stdout-json      Disable stdout json output
  -iet, --ignore-error-task  Continue child task even if parent failed
  -sjl, --save-json-log   Save task log in JSON file
  -i, --interactive       Enable interactive CLI mode
  -s, --silent            Run silently (no CLI interaction)
```

### Interactive Mode Commands

```bash
> help           # Show all available commands
> info           # Show workflow metadata
> show           # Show tasks in current level
> show-all       # Show all tasks
> go <index>     # Go to specific task
> get <field> <index>   # Get field of a task (stdout, stderr, pid, command, result, etc.)
> back           # Go to parent task
> clear          # Clear terminal
> exit           # Exit interactive mode
```

### Example 
```bash
#using yaml workflow
python3 ewe.py -t vulnweb.com -w workflow.yaml -o ./output
#using json workflow
python3 ewe.py -t vulnweb.com -w workflow.json -o ./output
```


---

## 🧬 Workflow Structure

### 🔹 Workflow Component

| Field | Description |
|-------|-------------|
| `name` | Workflow name |
| `description` | Workflow description |
| `tasks` | List of task objects (see below) |

---

### 🔸 Tasks Component

| Field | Description |
|-------|-------------|
| `name` | Task name |
| `description` | Task description |
| `command` | Shell command to execute |
| `result` | Path or value to save the result (e.g., `file.txt` or `subdir/file.txt`) |
| `wait_all` | Boolean - whether to wait for all siblings before executing children |
| `tasks` | Nested child tasks |

---

### 🧩 Command Placeholders

EWE supports dynamic placeholders in commands. These are replaced during execution.

| Placeholder | Replaced With |
|-------------|---------------|
| `{target}` | Value from `--target` CLI argument |
| `{name}` | Current task's name |
| `{result}` | Resolved result path for the task (e.g. `output/taskname.txt`) |
| `{output_path}` | Output directory path (`--output`) |
| `{parent_name}` | Parent task’s name (if exists), otherwise empty |
| `{parent_result}` | Parent task’s resolved result path (if exists), otherwise empty |

---

## 📁 Workflow Example (JSON)

```json
{
    "name": "sample workflow",
    "description": "sample workflow for execution",
    "tasks": [
        {
            "name": "Subdomain Finder",
            "description": "enumerate subdomain using subfinder",
            "result": "subdomains.txt",
            "command": "subfinder -d {target} -o {result}",
            "tasks": [
                {
                    "name": "Looking for HTTP\/S",
                    "description": "Scanning with HTTPX",
                    "result": "http_result.txt",
                    "command": "httpx -l {parent_result} -o {result}",
                    "wait_all": false,
                    "tasks": []
                }
            ]
        },
        {
            "name": "Collecting URLs",
            "description": "Collecting URLs using katana",
            "result": "urls.txt",
            "command": "katana -u {target} -o {result}",
            "tasks": []
        }
    ]
}
```

---

## 📁 Workflow Example (YAML)

```yaml
name: sample workflow
description: sample workflow for execution
tasks:
- name: Subdomain Finder
  description: enumerate subdomain using subfinder
  result: subdomains.txt
  command: subfinder -d {target} -o {result}
  tasks:
  - name: Looking for HTTP/S
    description: Scanning with HTTPX
    result: http_result.txt
    command: httpx -l {parent_result} -o {result}
    wait_all: false
    tasks: []
- name: Collecting URLs
  description: Collecting URLs using katana
  result: urls.txt
  command: katana -u {target} -o {result}
  tasks: []

```

---

## 🤝 Contributing

This project is far from perfect and open to contributions. Whether it's feature suggestions, bug reports, or pull requests — all are welcome! Let’s build something powerful together.

---

## 📜 License

MIT License. Do anything you want, but don't blame me 😄
