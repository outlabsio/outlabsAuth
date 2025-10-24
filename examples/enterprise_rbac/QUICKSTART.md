# Quick Start - Real Estate Example

**Status**: ✅ Ready to test immediately (MongoDB & Redis are running)

## Run in 3 Commands

```bash
# 1. Seed the database (creates all 5 scenarios)
cd examples/enterprise_rbac
python seed_data.py

# 2. Start the API
uvicorn main:app --reload --port 8001

# 3. Open Swagger UI in browser
open http://localhost:8001/docs
```

## Test Immediately

### Login & Explore

1. **Visit**: http://localhost:8001/docs
2. **Click**: "Authorize" button (top right)
3. **Login** with any of these accounts:

```
Franchise Executive:  exec@remax.com          / password123
Broker:               broker@remax-sv.com     / password123
Agent:                agent1@remax-sv.com     / password123
Support:              support@outlabs.com     / password123
```

4. **Try**:
   - `GET /api/leads` - See leads (different results per user!)
   - `GET /api/entities/suggestions` - Entity type suggestions
   - `GET /api/entities` - View entity hierarchy
   - `POST /api/leads` - Create a new lead

### What to Test

**Tree Permissions:**
- Login as `exec@remax.com` → Sees ALL franchise leads
- Login as `agent1@remax-sv.com` → Sees only Downtown Team leads

**Entity Flexibility:**
- RE/MAX uses "brokerage"
- Keller Williams uses "market_center"
- Both work seamlessly

**Entity Suggestions:**
- `GET /api/entities/suggestions?parent_id={id}`
- Shows existing entity types at that level

**Internal Teams:**
- Login as `support@outlabs.com` → Global access to ALL leads

## Files Created

```
examples/enterprise_rbac/
├── main.py           (600 lines)  - FastAPI application
├── models.py         (140 lines)  - Lead domain model
├── seed_data.py      (1000 lines) - 5 scenarios seeding
├── README.md         (400 lines)  - Complete documentation
├── REQUIREMENTS.md   (650 lines)  - Use case analysis
└── PROGRESS.md       (190 lines)  - Implementation tracker
```

**Total**: ~3,000 lines of code + documentation

## What's Included

### 5 Scenarios
1. RE/MAX National - 5-level hierarchy
2. RE/MAX Regional - 3 brokerages
3. Keller Williams - Different naming
4. Solo with Team - Minimal hierarchy
5. Solo Only - Flattest structure

### Data Created
- 13 roles
- 18 users
- 38+ entities
- 11 sample leads

### Features Demonstrated
- Entity hierarchy (flexible types)
- Tree permissions
- Entity type suggestions
- Granular permissions
- Internal teams
- Lead CRUD operations

## Next Steps

1. ✅ **Test the API** (run the 3 commands above)
2. **Connect Admin UI** (optional)
3. **Read full docs** in README.md

---

**Everything is ready to go!** 🚀
