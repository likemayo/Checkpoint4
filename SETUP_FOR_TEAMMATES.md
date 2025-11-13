# Setup Instructions for Team Members

## ⚠️ Important: Database is Local

**Each person has their own separate database!** When you run the app on your laptop, you get a fresh database. You won't have the accounts that someone else created on their laptop.

## Quick Setup (5 minutes)

### Option 1: Docker (Easiest) ✅ Recommended

1. **Start the application**
   ```bash
   docker-compose up
   ```
   Wait for the "Starting Flask application" message. 
   
   **✨ NEW: Database is automatically seeded on first startup!**
   
   You'll see messages like:
   - "Seeding database..."
   - "Inserted user: admin1"
   - "NOTE: Default admin account - username: admin1, password: 123"

2. **Access the app**
   - Open browser: http://localhost:5000
   - **Login credentials:**
     - **Admin**: `admin1` / `123`
     - **Customer**: `john` / `password123`

That's it! No manual seeding required. 🎉

### Option 2: Manual Setup

1. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize database**
   ```bash
   python -m src.main
   ```

4. **Seed demo accounts**
   ```bash
   python -m src.seed
   python -m db.seed_flash_sales
   ```

5. **Start the app**
   ```bash
   export APP_DB_PATH=$(pwd)/app.sqlite
   export ADMIN_API_KEY=admin-demo-key
   export APP_SECRET_KEY=dev-insecure-secret
   python -m src.app
   ```

6. **Access at http://localhost:5000**

## Default Accounts (After Seeding)

| Username | Password | Role |
|----------|----------|------|
| `admin1` | `123` | Admin (full access) |
| `john` | `password123` | Customer |
| `jane` | `password123` | Customer |
| `alice` | `password123` | Customer |

## Common Issues

### "Invalid username or password" when logging in as admin1

**Problem**: The database wasn't seeded (older setup) or seeding failed.

**Solution**: 
- **With Docker**: Restart with fresh database:
  ```bash
  docker-compose down -v
  docker-compose up
  ```
  The database will be automatically seeded on startup.

- **Without Docker**: Run the seed command manually:
  ```bash
  python -m src.seed
  ```

### Where is the database file?

**Docker**: Inside the container at `/app/data/app.sqlite` (persists in a Docker volume)

**Manual**: In your project directory: `./app.sqlite`

### I want to start fresh

**Docker**:
```bash
docker-compose down -v  # Delete volumes (database)
docker-compose up       # Start fresh
docker-compose exec web python -m src.seed  # Re-seed accounts
```

**Manual**:
```bash
rm app.sqlite
python -m src.main
python -m src.seed
```

## Testing the Setup

1. **Test customer login**: 
   - Go to http://localhost:5000
   - Login as `john` / `password123`
   - You should see the customer dashboard

2. **Test admin login**:
   - Go to http://localhost:5000
   - Login as `admin1` / `123`
   - You should be redirected to the admin dashboard

3. **Test RMA system**:
   - Make a test purchase as a customer
   - Request a return
   - Login as admin to process the return

## Need Help?

- Check the main [README.md](./README.md) for full documentation
- Look at [docs/Runbook.md](./docs/Runbook.md) for operational guidance
- Ask the team!
