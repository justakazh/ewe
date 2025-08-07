import argparse
import json
import subprocess
import threading
import os
import time
import signal
import sys
import textwrap
from tabulate import tabulate
from colorama import init, Fore, Style

# Auto-reset warna terminal setiap print
init(autoreset=True)


class TaskProcess:
    def __init__(self, args):
        self.args = args
        self.thread_lock = threading.Lock()
        self.log_file = os.path.join(args.output, "logs/logs.json")
        self.log_data = {}
        self.stop_event = threading.Event()
        self.active_processes = []
        self.was_stopped = False

        # Tangani sinyal agar proses bisa dihentikan dengan aman
        signal.signal(signal.SIGTERM, self.handle_sigterm)
        signal.signal(signal.SIGINT, self.handle_sigterm)

    def handle_sigterm(self, signum, frame):
        print("\n[!] Received termination signal (SIGTERM or SIGINT). Stopping tasks...")
        self.stop_event.set()
        self.was_stopped = True

        for proc in self.active_processes:
            if proc.poll() is None:
                try:
                    proc.terminate()
                    print(f"[x] Terminated process with PID {proc.pid}")
                except Exception as e:
                    print(f"[!] Error terminating process {proc.pid}: {e}")

        time.sleep(1)
        sys.exit(1)

    def main(self):
        os.makedirs(self.args.output, exist_ok=True)
        os.makedirs(os.path.join(self.args.output, "logs"), exist_ok=True)

        with open(self.args.workflow, "r") as f:
            decode_workflow = json.load(f)
        self.log_builder = self.createJsonLog(decode_workflow)

        self.save_log()

        if self.args.silent:
            self.run_task()
        elif self.args.interactive:
            self.task_thread = threading.Thread(target=self.run_task)
            self.task_thread.start()
            self.interactive_cli()
            self.task_thread.join()
        else:
            self.task_thread = threading.Thread(target=self.run_task)
            self.task_thread.start()
            self.print_tree()
            self.task_thread.join()
            if not self.task_thread.is_alive():
                self.clearScreen()
                self.banner()
                self.make_tree()
                print("\n[*] Workflow finished, output in folder: ", self.args.output)

    def run_task(self):
        threads = []
        for task in self.log_builder['tasks']:
            t = threading.Thread(target=self.run_task_process, args=(task,))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

    def run_task_process(self, task, parent_task=None):
        if self.stop_event.is_set():
            task['status'] = 'stopped'
            self.save_log()
            return

        command = self.setPlaceholder(task, parent_task)
        task['status'] = 'running'
        task['command'] = command
        self.save_log()

        try:
            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            task['pid'] = proc.pid
            self.active_processes.append(proc)
            self.save_log()

            stdout, stderr = proc.communicate()

            if not self.args.no_stdout_json:
                task['stdout'] = stdout

            task['error'] = stderr
            task['status'] = 'done' if proc.returncode == 0 else 'error'
            if self.stop_event.is_set():
                task['status'] = 'stopped'

            self.save_log()

        except Exception as e:
            task['status'] = 'error'
            task['error'] = str(e)
            self.save_log()
            return

        finally:
            if 'proc' in locals() and proc in self.active_processes:
                self.active_processes.remove(proc)

        # Jalankan task anak jika ada
        if 'tasks' in task and isinstance(task['tasks'], list):
            if self.args.ignore_error_task:
                self.run_child_tasks(task)
            else:
                if task['status'] in ['error', 'stopped', 'skipped']:
                    task = self.setStatusChild(task)
                    self.save_log()
                else:
                    self.run_child_tasks(task)

    def run_child_tasks(self, parent_task):
        threads = []
        for child_task in parent_task['tasks']:
            if self.stop_event.is_set():
                return

            if child_task.get('wait_all', False):
                while not self.is_all_parent_level_done(parent_task):
                    if self.stop_event.is_set():
                        return
                    time.sleep(0.5)

            t = threading.Thread(target=self.run_task_process, args=(child_task, parent_task))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

    def setStatusChild(self, task):
        for child_task in task['tasks']:
            child_task.update({
                'status': 'skipped',
                'stdout': '',
                'error': '',
                'pid': ''
            })
            if 'tasks' in child_task:
                child_task = self.setStatusChild(child_task)
        return task

    def is_all_parent_level_done(self, parent_task):
        for top_task in self.log_builder['tasks']:
            if top_task == parent_task:
                return all(t['status'] in ['done', 'skipped', 'error'] for t in self.log_builder['tasks'])
        return self._check_parent_level(self.log_builder['tasks'], parent_task)

    def _check_parent_level(self, tasks, parent_task):
        for task in tasks:
            if 'tasks' in task and parent_task in task['tasks']:
                return all(t['status'] in ['done', 'skipped', 'error'] for t in task['tasks'])
            elif 'tasks' in task:
                result = self._check_parent_level(task['tasks'], parent_task)
                if result is not None:
                    return result
        return None

    def setPlaceholder(self, task, parent_task=None):
        command = task['command']
        command = command.replace('{target}', self.args.target)
        command = command.replace('{name}', task['name'])
        command = command.replace('{result}', os.path.join(self.args.output, task.get('result', f"{task['name']}.txt")))
        command = command.replace('{output_path}', self.args.output)

        if parent_task:
            command = command.replace('{parent_name}', parent_task['name'])
            command = command.replace('{parent_result}', os.path.join(self.args.output, parent_task.get('result', f"{parent_task['name']}.txt")))
        else:
            command = command.replace('{parent_name}', '')
            command = command.replace('{parent_result}', '')

        return command

    def save_log(self):
        with self.thread_lock:
            with open(self.log_file, "w") as f:
                json.dump(self.log_builder, f, indent=4)

    def createJsonLog(self, node):
        if 'tasks' in node and isinstance(node['tasks'], list):
            for i, task in enumerate(node['tasks']):
                task.update({
                    'status': 'pending',
                    'stdout': '',
                    'error': '',
                    'pid': ''
                })
                task = self.createJsonLog(task)
                node['tasks'][i] = task
        return node

    # ========================
    # === INTERACTIVE MODE ===
    # ========================

    def interactive_cli(self):
        print("Interactive CLI")
        path = []

        while True:
            try:
                current = self.get_task_by_path(path)
                input_cmd = input(f"{'/' + '/'.join([t['name'] for t in path]) if path else '/'} > ").strip()
            except KeyboardInterrupt:
                print("\n[!] Exiting interactive mode.")
                break

            if input_cmd == 'exit':
                self.stop_event.set()
                break

            elif input_cmd == 'help':
                print(textwrap.dedent("""
                > help - show help
                > show - show task list
                > go <index> - go to task
                > get <field> <index> - get info of task (error, stdout, status, pid, command, description, result)
                > back - go back to parent task
                > clear - clear screen
                > exit - exit interactive mode
                """))

            elif input_cmd == 'show':
                tasks = current.get("tasks", [])
                if not tasks:
                    print("  [!] No subtasks.")
                    continue

                rows = []
                for i, t in enumerate(tasks):
                    name = t.get('name', '')
                    status = self.color_status(t.get('status', ''))
                    child_task = len(t.get('tasks', []))
                    rows.append([i, name, status, child_task])

                print(tabulate(rows, headers=["No", "Name", "Status", "Child Task"], tablefmt="grid"))

            elif input_cmd.startswith("go "):
                try:
                    idx = int(input_cmd.split()[1])
                    tasks = current.get("tasks", [])
                    path.append(tasks[idx])
                except:
                    print("  [!] Invalid index.")
                    continue

            elif input_cmd.startswith("get "):
                try:
                    field, idx = input_cmd.split()[1], int(input_cmd.split()[2])
                    tasks = current.get("tasks", [])
                    if field == 'result':
                        print(os.path.join(self.args.output, tasks[idx].get("result", f"{tasks[idx]['name']}.txt")))
                    else:
                        print(tasks[idx].get(field, ""))
                except:
                    print("  [!] Invalid command.")
                    continue

            elif input_cmd == 'back':
                if path:
                    path.pop()
                else:
                    print("  [!] Already at root.")
            elif input_cmd == 'clear':
                self.clearScreen()
            else:
                print(f"  [!] Unknown command: {input_cmd}")

    def wrap_text(self, text, width=50):
        return '\n'.join(textwrap.wrap(text, width=width))

    def color_status(self, status):
        color_map = {
            'done': Fore.GREEN,
            'running': Fore.YELLOW,
            'error': Fore.RED,
            'waiting': Fore.BLUE,
            'pending': Fore.BLUE,
            'stopped': Fore.LIGHTBLACK_EX,
            'skipped': Fore.LIGHTBLACK_EX
        }
        return color_map.get(status, '') + status + Style.RESET_ALL

    def get_task_by_path(self, path):
        task = self.log_builder
        for p in path:
            task = next((t for t in task.get("tasks", []) if t is p), task)
        return task

    def print_tree(self):
        try:
            while self.task_thread.is_alive():
                self.clearScreen()
                self.banner()
                print("[*] Workflow Progress\n")
                self.make_tree()
                print("\n[*] Take your coffee and please wait..")
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop_event.set()
            print("\n[!] Monitoring stopped by user.")

    def make_tree(self, tasks=None, indent=0):
        if tasks is None:
            tasks = self.log_builder.get("tasks", [])

        for task in tasks:
            name = task.get("name", "unknown")
            status = task.get("status", "waiting")
            icon, color = self.get_status_icon(status)

            indent_str = "  " * indent + ("└── " if indent > 0 else "")
            print(f"{indent_str}[{icon}] {color}{name}{Style.RESET_ALL} ({self.color_status(status)})")

            if "tasks" in task and isinstance(task["tasks"], list):
                self.make_tree(task["tasks"], indent + 1)

    def get_status_icon(self, status):
        icon_map = {
            'done': ("✓", Fore.GREEN),
            'running': ("~", Fore.YELLOW),
            'error': ("✗", Fore.RED),
            'waiting': (" ", Fore.CYAN),
            'pending': (" ", Fore.CYAN),
            'skipped': ("-", Fore.LIGHTBLACK_EX),
            'stopped': ("!", Fore.LIGHTBLACK_EX)
        }
        return icon_map.get(status, ("?", Fore.WHITE))
    def clearScreen(self):
        os.system("cls" if os.name == "nt" else "clear")
    def banner(self):
        print(textwrap.dedent("""
           _____      ______
          / __/ | /| / / __/
         / _/ | |/ |/ / _/  
        /___/ |__/|__/___/  
     Execution Workflow Engine
          @justakazh
        """))


def main():
    parser = argparse.ArgumentParser(description="Ewe CLI")
    parser.add_argument("-t", "--target", type=str, required=True, help="Target value")
    parser.add_argument("-w", "--workflow", type=str, required=True, help="Workflow JSON file")
    parser.add_argument("-o", "--output", type=str, required=True, help="Output folder")
    parser.add_argument("-iet", "--ignore-error-task", action="store_true", help="Ignore error task then process child task")
    parser.add_argument("-njs", "--no-stdout-json", action="store_true", help="No stdout json")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("-s", "--silent", action="store_true", help="Silent mode")
    args = parser.parse_args()

    runner = TaskProcess(args)
    runner.main()


if __name__ == "__main__":
    main()
