# HIPS Quick Start Guide

Get HIPS up and running in 5 minutes!

## Step 1: Start the Backend

```bash
cd C:\PSM\HIPS\backend
python -m  hips_service.main

```

Wait for:
```
✓ All components started successfully
✓ API server starting on 0.0.0.0:8000
```

## Step 2: Start the Frontend

Open a **new terminal**:

```bash
cd C:\PSM\HIPS\frontend
npm run dev 
```

Wait for:
```
➜  Local:   http://localhost:5173/
```

## Step 3: Open the Dashboard

Open browser to: **http://localhost:5173**

You should see the HIPS dashboard! 🎉

## Step 4: Test It Works

Run the complete test suite:

```bash
cd /home/sk/workspace/qriocity/cyber/HIPS/test_scripts
chmod +x test_all.sh
./test_all.sh
```

This will:
- Create processes (Python, Bash)
- Create files normally
- Simulate ransomware (rapid file changes)
- Create suspicious file extensions
- Run scripts from /tmp

## Step 5: View the Results

1. Go to **Alerts** page
2. You should see several alerts:
   - ⚠️ Ransomware rapid file changes (CRITICAL)
   - ⚠️ Suspicious file extensions (CRITICAL)
   - ℹ️ Python script execution (LOW)
   - ⚠️ Bash script from /tmp (MEDIUM)

3. Go to **Logs** page to see all events

## Common Issues

### Backend won't start
```bash
# Check if port 8000 is in use
sudo lsof -i :8000

# Check Python version (needs 3.9+)
python3 --version
```

### Frontend won't start
```bash
# Reinstall dependencies
cd frontend
rm -rf node_modules
npm install
```

### No events showing
```bash
# Check backend logs
tail -f backend/hips.log

# Make sure backend is running
curl http://localhost:8000/api/system/status
```

## Next Steps

1. Read the [User Guide](USER_GUIDE.md) for detailed instructions
2. Create your own detection rules
3. Customize the configuration

## File Locations

- **Rules:** `backend/rules/`
- **Config:** `backend/config/`
- **Database:** `backend/hips_data.db`
- **Logs:** `backend/hips.log`
- **Test Scripts:** `test_scripts/`

## Need Help?

Check:
- `USER_GUIDE.md` - Complete guide
- `README.md` - Project overview
- Backend logs: `backend/hips.log`
- Browser console: F12

Happy monitoring! 🛡️
