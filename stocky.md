# stocky

Stocky is a simple & flexible inventory management application for classroom supplies
It helps teachers and administrators track which students have borrowed supplies

## views

Stocky has a few views: 

+ Administration
    + User management
        + toggle-able table/card view with CRUD for users, organized in flexible & nestable groups. Permissions can be set at group level
        + users should have this schema:
            + UUID
            + Name
            + Status (Active / Inactive) — admins can optionally bar Inactive users from the kiosk
            + (dynamic) event history
            + (dynamic) current items on loan
        + Ability to generate or register a bar-code to a user
        + Ability to generate a User ID card for printing (single, whole-group, or a multi-up sheet)
        + Multi-select for batch edits (move group / set status / delete) and .xlsx import/export
    + Inventory management
        + Table of items in inventory with CRUD, allow drill-in to see history
        + CRUD should allow passive creation of multi-select properties - e.g. item type should be selected from drop-down but have a "add new" option that will open up form to create a new item type from the create/update item form
        + Defaults to "active" items (hides Lost/Discarded); search/filter on status, condition,
          type, location, barcode; a "needs review" banner filters flagged items
        + Multi-select for batch edits (type / location / condition / status / clear-review / delete)
          and .xlsx import/export (each row tagged C/U/D to create, update, or delete)
        + Ability to create item tags automatically for printing (single, whole-type, or multi-up)
    + History — a filterable, paginated log of every event (checkout, checkin, damage, loss, …)
    + Settings — app-level toggles (e.g. block Inactive users at the kiosk)
    + Export — a multi-up US-Letter sheet of every ID card and item tag, for bulk printing
        + Item types should have this schema: 
            + UUID
            + Name/Title
            + Manufacturer/Brand
            + Author (optional)
            + Publish date (optional)
            + Description
            + Photo
            + URL
            + Cost
            + UPC/ISBN
            + (dynamic, one-to-many) Items (items of this type)
        + Items should have this schema:
            + UUID
            + Item type
            + Name
            + Photo (from type by default)
            + Description (from type by default)
            + (dynamic) event history
            + (dynamic) Status — availability *derived from the event log*: Checked out, Available,
              Unavailable, Lost, Discarded. (Checked out / Available follow check-in/out;
              Unavailable/Lost/Discarded come from a damage/loss report or an explicit admin action.)
            + Condition — physical wear (stored, admin-editable): On order, New, Good, Fair, Worn,
              Damaged. (New becomes Good on first checkout; a damage report sets Damaged.)
            + Needs-review flag — auto-set when damage/loss is reported so an admin can triage; the
              admin clears it (or leaves it set)
            + Purchase price
            + Purchase date
            + Location
+ Check-in/out
    + User interface for checking in & checking out items. Note that this should automatically work with barcode readers - e.g. it should handle inputs from barcode readers and intelligently determine what to do without focus issues (some other apps have issues where you need to focus the right input box before scanning an item)
    + basic process
        + Scan ID card to login to user page
        + User page displays user's current items and statuses - click on item to open item modal
        + Scan item barcode to check item in/out, and show "more actions" button to open modal upon passive check-in/out. Default actions: 
            + Check-in if logged in user currently has item checked-out
            + Check-out if item is currently not checked-out
            + Open modal if item is currently checked out by another user
        + Item modal: action dialog for that item, with ability to check out, report damage, report loss, check-in. Add smart logic for items e.g. you can't check out an item that you already currently have checked out. 
        + Complete button to log user out, or timeout user. 
        + If another user scans their ID code, logout current user and login to new user's page
+ Inventory: View items in inventory and their locations and qtys in table or cards. Double-click to see item details and history. Search & filter. no CRUD in this view, this is for users only

## tech stack

This should be a pretty lightweight app, capable of running on a raspberry pi 4
Tech stack
+ Backend
    + Need makefile for make run dev, make down, etc
    + PostgreSQL 18 !!!DO NOT DOWNGRADE POSTGRESQL!!!
    + FastAPI 0.138 & SQLModel
    + UV for package, venv, dependency management, and for starting/stopping server. YOU SHALL NOT USE PIP
    + Python 3.13
+ Frontend
    + NPM for package management
    + Next.js 16.2
    + Radix UI with minimal styling
+ Docker-compose for easy deployment
+ Makefile for easy dev environment running