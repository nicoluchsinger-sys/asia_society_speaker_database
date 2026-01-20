import os

print("Current working directory:", os.getcwd())
print("\nLooking for .env file...")

if os.path.exists('.env'):
    print("✓ .env file exists")
    print("\nContents of .env file:")
    with open('.env', 'r') as f:
        contents = f.read()
        print(repr(contents))  # Shows exactly what's in the file
        
    # Try to parse it
    for line in contents.split('\n'):
        line = line.strip()
        if line.startswith('ANTHROPIC_API_KEY='):
            key = line.split('=', 1)[1].strip()
            print(f"\nFound key: {key[:10]}..." if len(key) > 10 else f"\nFound key: {key}")
            print(f"Key length: {len(key)}")
else:
    print("✗ .env file NOT found")

print("\nEnvironment variable ANTHROPIC_API_KEY:", os.getenv('ANTHROPIC_API_KEY'))