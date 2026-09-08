Step 0 — File setup
Create a new Figma file, name it VORA — NuxCine Hackathon 2026.
Create these Pages (the left sidebar, not app screens) to organize the file the way the brief asks for (identity, screens, flow, all in one file):
🎨 Design System
🔐 Auth & Legal
🧍 Passenger
🚗 Driver
🛠 Admin
🔀 User Flow
Set Figma's default frame size: mobile screens (Passenger/Driver/Auth) use 390×844 (iPhone 12/13 size — a safe, common mobile frame). Admin screens use 1440×900 (desktop, since admin-layout is a sidebar+content layout, not mobile).
Step 1 — Design System page (do this first, everything else reuses it)
Color styles (create these as Figma Color Styles, exact hex from our CSS variables)
Style name	Hex	Used for
bg/default	
#e7ece9	Page background
bg/alt	
#dce6e2	Gradient end (map screens)
surface/default	
#ffffff	Cards, panels
surface/muted	
#f3f6f4	Stat cards, secondary buttons
border/default	
#a2bbb3	Borders, dividers
text/default	
#17212b	Body text
primary/default	
#285e55	Primary buttons, links, active states
primary/hover	
#1f4a43	Button hover
accent/default	
#45756d	Eyebrow labels, muted accents
danger/default	
#c0392b	SOS button, errors
rating/gold	
#d4a017	Filled star rating
admin/sidebar-bg	
#16241f	Admin sidebar background
Typography styles
Style name	Font	Size/weight	Used for
Heading/H1	Georgia (serif)	32–52px, regular (400)	Page titles
Heading/H2	Georgia (serif)	24–29px, regular	Section headers
Heading/H3	Georgia (serif)	18px, regular	Card titles (driver name, etc.)
Body/Default	Arial	15px, regular	Paragraph text
Label/Eyebrow	Arial	14px, bold	Small status labels above headings (not uppercase — we deliberately removed the tracked-caps look)
Label/Button	Arial	15px, bold	Button text
Label/Small	Arial	12px, bold, uppercase, 0.05em tracking	Table headers, stat labels only
Effects
Style name	Value	Used for
shadow/map-panel	X:0 Y:18 Blur:45, 
#243d39 at 18% opacity	Map container shadow
radius/standard	8px corner radius	Buttons, cards
radius/panel	10px corner radius	Larger panels, admin table
radius/pill	999px	Status badges and notification counts ONLY — never buttons
Step 2 — Reusable components (build once, instance everywhere)

Build each of these as a Figma Component on the Design System page — this is what makes the remaining 30 screens fast, since you drag instances instead of rebuilding each element.

Button/Primary — 
#285e55 fill, white text, 8px radius, 12px vertical / 20px horizontal padding.
Button/Secondary — 
#f3f6f4 fill, 
#17212b text, 8px radius, 1px 
#a2bbb3 border.
Button/SOS — 
#c0392b fill, white text, full-width, 8px radius.
Input/Text — white fill, 1px 
#a2bbb3 border, 6px radius, 10px padding.
Nav/BottomNav — white bar, 3 items (Home/History/Profile for passenger; Dashboard/Earnings/History/Profile for driver), active item in primary/default.
Nav/AdminSidebar — 
#16241f fill, 200px wide, 6 nav items, active item pill in primary/default.
Card/Stat — surface/muted fill, centered big number (H2 style) + small label underneath.
Card/RideSummary — white surface, border, holds origin/destination/fare rows.
Badge/Status — pill shape, border, used for things like "Available"/"Offline."
Badge/NotificationCount — small red pill, white bold number, top-right corner anchor.
Star/Rating — 5-star row, filled = 
#d4a017, empty = 
#cccccc.
Map/Placeholder — a rectangle with shadow/map-panel, light green-gray fill (
#dce6e2), label text "Map" centered — stand-in since Figma can't render a live Mapbox instance.
Step 3 — Screens, page by page

For every screen: create the frame at 390×844 (or 1440×900 for admin), name it exactly as listed (this naming matters for step 4's flow connections), and place the listed elements using the components above.

🔐 Auth & Legal (5 frames)
Frame name	Contents
Auth/Splash	Centered: "VORA" (H1), "Smart mobility for Cameroon" (eyebrow), Button/Primary "Get started"
Auth/Login	H1 "Log in", Input "Phone number", Input "Password", Button/Primary "Log in", text link "Sign up" below
Auth/Signup	H1 "Create account", Input "Full name", Input "Phone number", Input "Password", Button/Primary "Sign up"
Legal/Privacy	H1 "Privacy Policy", eyebrow "Last updated: September 2026", 6 H3+paragraph blocks (What we collect / Why / Who sees it / SOS data / Retention / Contact) — copy exactly from the page code
Legal/Terms	Same layout pattern, 6 sections (What VORA is / Using the app / Payment / Conduct & safety / Cancellations / Changes)
🧍 Passenger (11 frames)
Frame name	Contents
Passenger/Home	Eyebrow "Bonjour, Aminata", H1 "Where are you going?", NotificationBell top-right, search-bar-style button "🔍 Enter your destination", BottomNav
Passenger/MapBooking	Map/Placeholder full-width, floating panel below with Input "Pickup" (prefilled), Input "Destination", Card/RideSummary-style price row, Button/Primary "Confirm ride" — this is the map-shell layout, so give the map ~60% of frame height
Passenger/Confirm	H1 "Confirm your ride", Card/RideSummary (From/To/Distance/Fare rows), Button/Primary "Confirm ride"
Passenger/Searching	Centered layout: pulsing dot graphic, H2 "Looking for a driver...", small text "This won't take long"
Passenger/DriverEnRoute	Map/Placeholder, header row: eyebrow "Driver on the way" + H1 "6 min away" + Badge/Status "Pickup: [location]", below: driver name/rating (H3), vehicle text, two Button/Secondary ("Message driver"/"Call driver")
Passenger/RideInProgress	Map/Placeholder, panel: driver name + rating, vehicle, "Heading to [destination]", Button/SOS full-width
Passenger/RideCompleted	Centered: H1 "Ride completed", fare text, Star/Rating row (interactive-looking, some filled), Button/Primary "Done"
Passenger/History	H1 "Ride history", repeated list rows (route + date + fare), BottomNav
Passenger/Profile	H1 "Profile", rows for Name/Phone/Rating, two Button/Secondary ("Edit profile"/"Log out"), links to Privacy/Terms, BottomNav
Passenger/Support	H1 "Support", contact info list (phone/email), a text-area shape, Button/Primary "Send"
Passenger/Notifications	H1 "Notifications", repeated list items (title bold + body + small timestamp), unread ones full-opacity, read ones dimmed
🚗 Driver (10 frames)
Frame name	Contents
Driver/Dashboard	H1 "Driver dashboard", Badge/Status toggle top-right ("Available"/"Offline" — show both states as two small variants), status text below
Driver/IncomingRequest	Centered: H2 "New ride request", Card/RideSummary (passenger, pickup, drop-off, fare), two buttons side by side (Secondary "Decline" / Primary "Accept")
Driver/RideAccepted	H1 "Ride accepted", pickup location text, passenger name/phone, Button/Primary "Start navigation"
Driver/Navigation	Map/Placeholder, panel: "Heading to pickup: [location]", Button/Primary "Arrived at pickup"
Driver/RideInProgress	Two states in one frame or two variants: (1) PIN entry — H2 + 4-digit input + Button/Primary "Start ride"; (2) in-progress — H2 "Ride in progress" + destination text + Button/Primary "End ride"
Driver/EndRide	Centered: H1 "Ride completed", fare collected line, commission line (15%), Button/Primary "Back to dashboard"
Driver/Earnings	H1 "Earnings", Card/Stat (big total), list of past rides with amounts, BottomNav
Driver/History	H1 "Ride history", list rows (route + date), BottomNav
Driver/Profile	H1 "Driver profile", Name/Vehicle/Rating rows, Button/Secondary "Edit profile", BottomNav
Driver/Safety	Centered: H1 "Safety", Button/SOS "Trigger emergency alert", three Button/Secondary ("Report a passenger"/"Contact assistance"/"Share this ride")
🛠 Admin (6 frames, 1440×900 desktop layout)

Every admin frame shares the same base: Nav/AdminSidebar on the left (fixed 200px), content area to the right.

Frame name	Contents
Admin/Dashboard	3× Card/Stat in a row (Active rides / Online drivers / Total users)
Admin/Users	Table: Name / Role / Status / Action-button columns, a few sample rows
Admin/Drivers	Table: Name / Vehicle / Status columns
Admin/Rides	Table: ID / Passenger / Driver / Status / Fare columns
Admin/Stats	3× Card/Stat, same style as Dashboard but framed as "Statistics"
Admin/Reports	List items: report type (bold) + ride reference + note + status
Step 4 — User flow connections (this is what actually satisfies "parcours utilisateur")

On the 🔀 User Flow page, drag instances of every frame you built (not copies — actual instances, so edits stay in sync) and use Figma's Prototype tab to draw connection arrows in this order:

Auth/Splash → Auth/Login → Passenger/Home → Passenger/MapBooking
→ Passenger/Confirm → Passenger/Searching → Passenger/DriverEnRoute
→ Passenger/RideInProgress → Passenger/RideCompleted → Passenger/Home
Driver/Dashboard → Driver/IncomingRequest → Driver/RideAccepted
→ Driver/Navigation → Driver/RideInProgress → Driver/EndRide → Driver/Dashboard

Select each frame, drag from its right-edge connection point to the next frame, choose "Navigate to" as the interaction — this is literally what the brief means by needing "les interactions principales" documented, and it's the part that's easy to skip but actually required.

Suggested build order, given your remaining time
Design System page (colors/type/components) — do this once, carefully, it pays for itself immediately.
Passenger frames (heaviest-weighted system in the brief).
Driver frames.
Auth + Legal (fastest, simplest layouts).
Admin (lowest priority per the brief's own wording).
User Flow connections last, once frames exist to connect.