#!/bin/bash
# Setup script for Gradle Artifactory Migration Tool

echo "Setting up Gradle Artifactory Migration Tool..."

# Make Python scripts executable
chmod +x gradle_artifactory_migrator.py
chmod +x batch_processor.py
chmod +x validate_setup.py

# Create necessary directories
mkdir -p templates
mkdir -p logs
mkdir -p reports

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file from template. Please update it with your Artifactory credentials."
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Run validation
echo "Running setup validation..."
python validate_setup.py

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Update .env file with your Artifactory credentials"
echo "2. Create a list of repositories to migrate (see repos.example.txt)"
echo "3. Run validation: python validate_setup.py"
echo "4. Start migration: python gradle_artifactory_migrator.py --help"