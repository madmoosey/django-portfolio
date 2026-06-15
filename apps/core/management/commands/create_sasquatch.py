import secrets
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates a superuser named sasquatch with a random password that is shown once.'

    def handle(self, *args, **kwargs):
        username = 'sasquatch'
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f"Superuser '{username}' already exists. No action taken."))
            return

        # Generate a secure 24-character random password
        password = secrets.token_urlsafe(18)
        
        # Create the superuser
        user = User.objects.create_superuser(
            username=username,
            email='sasquatch@arborwatch.net',
            password=password
        )
        
        # Output the credentials exactly once
        self.stdout.write(self.style.SUCCESS(f"Successfully created superuser '{username}'."))
        self.stdout.write(self.style.WARNING("=" * 50))
        self.stdout.write(self.style.WARNING("SAVE THIS PASSWORD NOW. IT WILL NOT BE SHOWN AGAIN."))
        self.stdout.write(self.style.WARNING(f"Username: {username}"))
        self.stdout.write(self.style.WARNING(f"Password: {password}"))
        self.stdout.write(self.style.WARNING("=" * 50))
