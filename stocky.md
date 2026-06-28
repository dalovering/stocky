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
            + (dynamic) event history
            + (dynamic) current items on loan
        + Ability to generate or register a bar-code to a user
        + Ability to generate a User ID card for printing
    + Inventory management
        + Table of items in inventory with CRUD, allow drill-in to see history
        + CRUD should allow passive creation of multi-select properties - e.g. item type should be selected from drop-down but have a "add new" option that will open up form to create a new item type from the create/update item form
        + Ability to create item tags automatically for printing
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
            + (dynamic) current status
            + Purchase price
            + Purchase date
            + Location
            + Condition (New, Used, Lost, Damaged, Discarded)
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