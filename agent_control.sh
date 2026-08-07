#!/usr/bin/env bash
set -e

ACTION=$1
if [ "$ACTION" != "start" ] && [ "$ACTION" != "stop" ] && [ "$ACTION" != "restart" ]; then
    echo "Usage: $0 {start|stop|restart}"
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="${PROJECT_ROOT}/.agent_runtime"
STATUS_PATH="${RUNTIME_DIR}/status.json"
LAUNCH_PATH="${RUNTIME_DIR}/launcher.json"
PYTHON_PATH="${PROJECT_ROOT}/.venv/bin/python"

mkdir -p "$RUNTIME_DIR"

if ! command -v jq &> /dev/null; then
    echo "jq is required but not installed. Please install jq (e.g. sudo apt install jq or brew install jq)."
    exit 1
fi

read_json() {
    local path="$1"
    local key="$2"
    if [ -f "$path" ]; then
        jq -r "$key // empty" "$path" 2>/dev/null || echo ""
    else
        echo ""
    fi
}

write_status_stopped() {
    if [ -f "$STATUS_PATH" ]; then
        local tmp="${STATUS_PATH}.tmp"
        jq '.state = "stopped" | .updated_at = (now | strftime("%Y-%m-%dT%H:%M:%SZ"))' "$STATUS_PATH" > "$tmp" 2>/dev/null || echo '{"state":"stopped"}' > "$tmp"
        mv "$tmp" "$STATUS_PATH"
    fi
}

write_launcher() {
    local agent_pid="$1"
    local monitor_pid="$2"
    local tmp="${LAUNCH_PATH}.tmp"
    jq -n --arg apid "$agent_pid" --arg mpid "$monitor_pid" \
       '{agent_launcher_pid: $apid, monitor_pid: $mpid, updated_at: (now | strftime("%Y-%m-%dT%H:%M:%SZ"))}' > "$tmp"
    mv "$tmp" "$LAUNCH_PATH"
}

get_process() {
    local pid="$1"
    local script_name="$2"
    if [ -n "$pid" ] && [ "$pid" != "null" ]; then
        if ps -p "$pid" -o args= 2>/dev/null | grep -Fqw "$script_name"; then
            echo "$pid"
            return
        fi
    fi
    echo ""
}

find_venv_process() {
    local script_name="$1"
    pgrep -f "${PYTHON_PATH}.*${script_name}" | head -n 1
}

stop_process_tree() {
    local parent_pid="$1"
    if [ -n "$parent_pid" ] && [ "$parent_pid" != "null" ]; then
        # Recursively kill children
        pkill -P "$parent_pid" 2>/dev/null || true
        # Kill the parent
        kill -9 "$parent_pid" 2>/dev/null || true
    fi
}

start_agent() {
    if [ ! -f "$PYTHON_PATH" ]; then
        echo "Virtual environment not found. Run 'uv sync' in $PROJECT_ROOT first."
        exit 1
    fi

    local launch_agent_pid=$(read_json "$LAUNCH_PATH" ".agent_launcher_pid")
    local status_pid=$(read_json "$STATUS_PATH" ".pid")
    local monitor_pid=$(read_json "$LAUNCH_PATH" ".monitor_pid")

    local agent_pid=$(get_process "$launch_agent_pid" "supervisor.py")
    [ -z "$agent_pid" ] && agent_pid=$(get_process "$launch_agent_pid" "main.py")
    [ -z "$agent_pid" ] && agent_pid=$(find_venv_process "supervisor.py")
    [ -z "$agent_pid" ] && agent_pid=$(find_venv_process "main.py")
    [ -z "$agent_pid" ] && agent_pid=$(get_process "$status_pid" "main.py")

    if [ -z "$agent_pid" ]; then
        nohup "$PYTHON_PATH" -u supervisor.py > "$RUNTIME_DIR/agent.out.log" 2> "$RUNTIME_DIR/agent.err.log" < /dev/null &
        agent_pid=$!
        echo "Started agent PID $agent_pid."
    else
        echo "Agent is already running (PID $agent_pid)."
    fi

    local m_pid=$(get_process "$monitor_pid" "monitor.py")
    [ -z "$m_pid" ] && m_pid=$(find_venv_process "monitor.py")

    if [ -z "$m_pid" ]; then
        if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
            nohup "$PYTHON_PATH" monitor.py > /dev/null 2>&1 < /dev/null &
            m_pid=$!
            echo "Opened monitor PID $m_pid."
        else
            echo "No display found. Skipping graphical monitor."
            m_pid="null"
        fi
    fi

    write_launcher "$agent_pid" "$m_pid"
}

stop_agent() {
    local launch_agent_pid=$(read_json "$LAUNCH_PATH" ".agent_launcher_pid")
    local status_pid=$(read_json "$STATUS_PATH" ".pid")
    
    local agent_pid=$(get_process "$launch_agent_pid" "supervisor.py")
    [ -z "$agent_pid" ] && agent_pid=$(get_process "$launch_agent_pid" "main.py")
    [ -z "$agent_pid" ] && agent_pid=$(find_venv_process "supervisor.py")
    [ -z "$agent_pid" ] && agent_pid=$(find_venv_process "main.py")
    
    if [ -z "$agent_pid" ]; then
        echo "Agent is not running."
    else
        stop_process_tree "$agent_pid"
        echo "Stopped agent process tree at PID $agent_pid."
    fi

    if [ -n "$status_pid" ] && [ "$status_pid" != "null" ]; then
        if [ -n "$(get_process "$status_pid" "main.py")" ]; then
            stop_process_tree "$status_pid"
        fi
    fi

    local monitor_pid=$(read_json "$LAUNCH_PATH" ".monitor_pid")
    local m_pid=$(get_process "$monitor_pid" "monitor.py")
    [ -z "$m_pid" ] && m_pid=$(find_venv_process "monitor.py")
    
    if [ -n "$m_pid" ] && [ "$m_pid" != "null" ]; then
        stop_process_tree "$m_pid"
        echo "Stopped monitor process at PID $m_pid."
    fi

    write_launcher "null" "null"
    write_status_stopped
}

# Use flock to ensure exclusive access
(
    flock -x -w 10 200 || { echo "Another agent start or stop operation is still running."; exit 1; }
    
    case "$ACTION" in
        start)
            start_agent
            ;;
        stop)
            stop_agent
            ;;
        restart)
            stop_agent
            start_agent
            ;;
    esac
) 200>"$RUNTIME_DIR/agent_control.lock"
