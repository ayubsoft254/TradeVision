version: '3.8'

services:
  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data/
    environment:
      POSTGRES_DB: tradevision
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5433:5432"  # Changed external port to 5433

  redis:
    image: redis:7-alpine
    ports:
      - "6380:6379"  # Changed external port to 6380

  web:
    build: .
    volumes:
      - .:/app
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    ports:
      - "7373:7373"
    environment:
      - DEBUG=1
    depends_on:
      - db
      - redis
    env_file:
      - .env

  celery:
    build: .
    command: |
      sh -c "
        python -c \"
import socket, time, sys
def wait_for_port(host, port, timeout=60):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0: sys.exit(0)
        except: pass
        time.sleep(0.1)
    sys.exit(1)
wait_for_port('db', 5432)
        \" &&
        celery -A tradevision worker --loglevel=info
      "
    volumes:
      - .:/app
    depends_on:
      - db
      - redis
    env_file:
      - .env

  celery-beat:
    build: .
    command: |
      sh -c "
        python -c \"
import socket, time, sys
def wait_for_port(host, port, timeout=60):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0: sys.exit(0)
        except: pass
        time.sleep(0.1)
    sys.exit(1)
wait_for_port('db', 5432)
        \" &&
        celery -A tradevision beat --loglevel=info
      "
    volumes:
      - .:/app
    depends_on:
      - db
      - redis
    env_file:
      - .env

volumes:
  postgres_data:
  static_volume:
  media_volume: