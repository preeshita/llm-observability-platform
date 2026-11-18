LLM Observability Platform --- Troubleshooting README


1. Purpose
  - Keep a quick reference for project setup, local URLs, common
    errors, and fixes.
  - Current implementation uses a mock AI response. It does not
    call a paid AI API.
  - Add new issues, questions, commands, and solutions to this
    document as the project progresses.
1. Project environment
- Project folder: D:\PROJECTS\llm-observability-platform
- Operating system: Windows
- Shell: PowerShell
- Python: 3.12.10
- Virtual environment: .venv
- Activate the virtual environment (run from the project folder):
  - .\.venv\Scripts\Activate.ps1
- Expected terminal prefix: (.venv)
- Use this command to run tests:
  - python -m pytest -v
  - Prefer this over pytest -v in this project because it reliably
    invokes pytest through the active Python interpreter.
2. Important local URLs
- FastAPI home: http://127.0.0.1:8000/
- FastAPI health check: http://127.0.0.1:8000/health
- FastAPI Swagger / interactive API docs:
  http://127.0.0.1:8000/docs
- FastAPI Prometheus metrics endpoint:
  http://127.0.0.1:8000/metrics
- Prometheus UI: http://localhost:9090/
- Prometheus targets / target health:
  http://localhost:9090/targets
- Prometheus query page: http://localhost:9090/graph
- Note about the Prometheus port: The docker run command used so
  far maps host port 9090 to container port 9090 (-p 9090:9090).
  Therefore, use port 9090. If a different host port was configured,
  use that host port instead.
3. Start the services
- Start Docker Desktop
  - Open Docker Desktop from the Windows Start menu.
  - Wait until Docker Desktop reports that the engine is running /
    Docker is ready.
  - Verify the Docker engine:
    - docker version
    - The output should include both Client and Server
      sections.
- Start FastAPI
  - Open PowerShell / VS Code terminal.
  - Navigate to the project root:
    - cd D:\PROJECTS\llm-observability-platform
  - Activate .venv if it is not already active:
    - .\.venv\Scripts\Activate.ps1
  - Start the API:
    - uvicorn main:app --reload
  - Keep this terminal open while Prometheus is scraping the API.
- Start Prometheus
  - Open a second PowerShell terminal.
  - Navigate to the project root:
    - cd D:\PROJECTS\llm-observability-platform
  - Run:
    - docker run --name prometheus -p 9090:9090 -v "${PWD}/monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml" prom/prometheus
  - Keep this terminal open while running the container in the
    foreground.
  - Open http://localhost:9090/targets and confirm the target is
    UP.
4. Prometheus configuration for the current setup
- Current setup
  - FastAPI runs directly on the Windows host at port 8000.
  - Prometheus runs inside Docker.
  - Because FastAPI is not currently a Docker Compose service,
    Prometheus must reach it through host.docker.internal, not the
    Docker service name app.
- File: monitoring/prometheus/prometheus.yml
- Expected contents:
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: "llm-observability"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["host.docker.internal:8000"]
- Important hostname differences
  - host.docker.internal:8000 --- use this now: Prometheus is in
    Docker and FastAPI runs on Windows.
  - app:8000 --- use this later when FastAPI and Prometheus run as
    services on the same Docker Compose network.
  - localhost:8000 --- from inside the Prometheus container, this
    refers to the Prometheus container itself, not the Windows host.
5. Restart Prometheus
- If Prometheus was started with the container name prometheus:
  - Stop it:
    - docker stop prometheus
  - Remove the stopped container:
    - docker rm prometheus
  - Make sure the terminal is at the project root:
    - cd D:\PROJECTS\llm-observability-platform
  - Start it again with the current configuration:
    - docker run --name prometheus -p 9090:9090 -v "${PWD}/monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml" prom/prometheus
- Check whether the container is running:
  - docker ps
- View Prometheus logs:
  - docker logs prometheus
- If the container already exists and you only need to restart it
  without changing its configuration:
  - docker restart prometheus
- If prometheus.yml has changed:
  - Restarting an existing container may not reload the file
    automatically.
  - For the simplest reliable reset with the current command, use
    docker stop prometheus, docker rm prometheus, then run the
    docker run command again.
- If Docker reports that the name /prometheus is already in use:
  - Check containers:
    - docker ps -a
  - Stop and remove the old Prometheus container if appropriate:
    - docker stop prometheus
    - docker rm prometheus
  - Run the start command again.
6. Issues encountered and solutions
- Issue 1 --- pytest -v fails with
  ModuleNotFoundError: No module named 'main'
  - When it happened: Pytest collection failed while importing
    from main import app in tests/test_main.py.
  - Cause / diagnosis: The direct pytest launcher did not
    resolve the project module correctly in that invocation.
  - Solution: Run pytest as a Python module from the project
    root:
    - cd D:\PROJECTS\llm-observability-platform
    - python -m pytest -v
  - Verified result: 6 passed.
  - Useful check:
    python -c "import main; print(main.__file__)" should print the
    project's main.py path.
  - Environment check commands:
    - where.exe python
    - where.exe pytest
    - python --version
    - python -m pytest --version
- Issue 2 --- Uvicorn error: Could not import module "main"
  - When it happened: Uvicorn was started from
    D:\PROJECTS\llm-observability-platform\monitoring\prometheus.
  - Cause: The terminal's current working directory was a
    subfolder. The project's main.py is in the project root.
  - Solution:
    - cd D:\PROJECTS\llm-observability-platform
    - uvicorn main:app --reload
  - Rule: Start uvicorn main:app --reload from the project
    root, where main.py is located.
- Issue 3 --- Docker error: cannot connect to
  npipe:////./pipe/docker_engine
  - Error example:
    failed to connect to the docker API ... The system cannot find the file specified.
  - Cause: Docker Desktop / Docker Engine was not running or had
    not finished starting.
  - Solution:
    - Open Docker Desktop.
    - Wait until the engine is running / Docker is ready.
    - Run docker version.
    - Confirm that both Client and Server information are
      displayed.
    - Retry the Prometheus docker run command.
  - Keep Docker Desktop running while using Docker containers.
- Issue 4 --- Prometheus target error:
  lookup app ... no such host
  - Error example:
    Error scraping target: Get "http://app:8000/metrics": dial tcp: lookup app ... no such host
  - Cause: Prometheus was configured to scrape app:8000, but
    FastAPI was running directly on Windows, not as a Docker service
    named app.
  - Solution for the current setup:
    - Edit monitoring/prometheus/prometheus.yml.
    - Set the target to host.docker.internal:8000.
    - Save the file.
    - Recreate the Prometheus container using the restart
      instructions in Section 5.
    - Open http://localhost:9090/targets.
    - Confirm that the llm-observability target shows UP.
  - Future change: When the project moves to Docker Compose and
    FastAPI is a service named app on the same Docker network as
    Prometheus, change the target to app:8000.
7. Stage 2 --- Automated test reference
- Test file: tests/test_main.py
- Run all tests:
  - python -m pytest -v
- Last verified result:
  - 6 passed in 1.40s
- Tests that passed:
  - test_home
  - test_health
  - test_ask_success
  - test_ask_empty_question
  - test_ask_missing_question
  - test_metrics_endpoint
8. Stage 3 --- Prometheus verification
- Before checking Prometheus:
  - Docker Desktop / Docker Engine is running.
  - FastAPI is running from the project root on port 8000.
  - Prometheus container is running.
  - monitoring/prometheus/prometheus.yml uses
    host.docker.internal:8000 for the current host-run API setup.
- Check target health:
  - Open http://localhost:9090/targets.
  - The llm-observability target should show UP.
- Check metrics directly:
  - Open http://127.0.0.1:8000/metrics.
  - Look for metric families such as:
    - llm_requests_total
    - llm_request_latency_seconds
    - llm_tokens_total
    - llm_errors_total
- Generate sample traffic:
  - Open http://127.0.0.1:8000/docs.
  - Use POST /ask with a JSON body such as:
    - {"question": "What is Kubernetes?"}
  - Refresh the Prometheus query page / run a query after the scrape
    interval.
9. Git and secrets reminders
- Keep .env private.
  - .env is ignored by .gitignore; never commit API keys or
    secrets.
  - Never paste API keys into chat, screenshots, logs, or source
    files.
- Keep generated/local folders out of Git:
  - .venv/
  - __pycache__/
  - .pytest_cache/
- Check Git status before committing:
  - git status --short
  - .env and .venv should not appear as untracked files.
- Current known Git status at the last check:
  - .gitignore and main.py were untracked and ready to be added
    when appropriate.
10. Running project checklist
- [ ] Docker Desktop is open and Docker Engine is running.
- [ ] PowerShell is at D:\PROJECTS\llm-observability-platform.
- [ ] .venv is active.
- [ ] FastAPI is running with uvicorn main:app --reload.
- [ ] FastAPI /docs opens.
- [ ] FastAPI /metrics opens.
- [ ] Prometheus container is running (docker ps).
- [ ] Prometheus target is UP at http://localhost:9090/targets.
- [ ] Tests pass with python -m pytest -v.
11. Update log
- Stage 1 --- FastAPI mock API and Prometheus metrics
  - Implemented mock /ask endpoint.
  - Added request count, latency, token, and error metrics.
- Stage 2 --- Pytest
  - Added and ran six tests.
  - All six tests passed using python -m pytest -v.
- Stage 3 --- Prometheus
  - Started Docker Desktop and Prometheus container.
  - Corrected scrape target for the current setup to
    host.docker.internal:8000.
  - Next verification: Confirm target health is UP at
    /targets.
- Future updates
  - Add each new issue, exact error message, root cause, fix, useful
    command, and relevant local URL to the matching section.
  - Update the running checklist and update log as each project
    stage is completed.


    ---MY WORK

    USEFUL DOCKER COMMANDS 

docker ps
docker ps -a
docker compose logs -f app
docker compose logs -f prometheus
docker compose logs -f grafana
docker compose restart
docker compose down
docker compose up -d



API: http://127.0.0.1:8000
documentation: http://127.0.0.1:8000/docs
Health: http://127.0.0.1:8000/health
Metrics: http://127.0.0.1:8000/metrics
promethues: http://localhost:9090
promethus target: http://localhost:9090/targets
grafana: http://localhost:3000
http://us.cloud.langfuse.com/project/cmw43o8e40404ad0elc3efaoy/traces
