#!/bin/bash

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "PostgreSQL started"

# Run migrations
echo "Running database migrations..."
python manage.py migrate

# Create superuser if it doesn't exist (optional)
echo "Creating superuser if needed..."
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    print("Creating superuser...")
    # You can uncomment and modify these lines to create a default superuser
    # User.objects.create_superuser(
    #     email='admin@tradevision.com',
    #     password='admin123',
    #     first_name='Admin',
    #     last_name='User'
    # )
    print("Remember to create a superuser manually with: python manage.py createsuperuser")
else:
    print("Superuser already exists")
EOF

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start the Django development server
echo "Starting Django server..."
exec python manage.py runserver 0.0.0.0:7373