# EmCare demo personas

Two demo users. Both live in `backend/data/seed.json`, keyed by user id (`maya`, `jasmine`). The frontend has a persona switcher so we can demo both journeys. All external data (wearables, Strava, cycle/pregnancy apps, calendar, records) is MOCKED in seed data. No real integrations today.

---

## Persona 1: Maya (`maya`), 27, finance analyst and marathon trainee

Maya works 60+ hour weeks at an investment firm in NYC and travels for client meetings 2-3 times a month. She's training for her first marathon in 16 weeks. She wears an Apple Watch or Garmin, logs runs in Strava, and tracks her cycle in an app she rarely opens. She's healthy but runs on caffeine, eats on the go, and sleeps poorly when traveling. She hasn't had a physical in over two years because she keeps putting it off.

**Goals:** Finish the marathon injury-free, keep her energy up at work, and stop letting health tasks slip.

**Frustrations:** Data is scattered across apps, she has no time to book appointments, training plans don't adapt to travel or bad sleep, and generic nutrition advice doesn't fit her schedule.

**How she uses the app:** Short bursts on her phone between meetings, longer weekly check-in on her laptop on Sunday.

### What Maya needs, by pane
- **Onboarding:** Setup in under 3 minutes. One-tap connections to watch, Strava, cycle app. Race date as main goal.
- **Dashboard:** Readiness score (sleep, HRV, recovery), today's run, one nutrition tip, travel alert ("You're in Chicago Tues-Thurs, plan adjusted").
- **Data connections:** Garmin or Apple Watch, Strava, cycle tracker, calendar (detect travel and busy weeks).
- **Appointments:** Suggests overdue annual physical, sports medicine or PT check before peak mileage, baseline bloodwork. Books into open calendar slots, ideally early mornings or near the office.
- **Post-appointment:** Quick voice or text note, e.g. "doctor recommended iron supplement, recheck in 8 weeks."
- **Labs:** Endurance markers: ferritin, iron, vitamin D, B12, thyroid. Plain-language flags ("Low ferritin can cause fatigue on long runs").
- **Mood and symptoms:** 10-second check-in on energy, stress, soreness, cycle phase. Highlights links like low energy during heavy work weeks.
- **Nutrition:** Fueling around long runs, iron-rich meals, hydration, options for airports, hotels, client dinners.
- **Workouts:** Marathon plan that adapts to cycle, sleep, travel, workload. Swaps tempo for easy run or hotel treadmill when needed. Strength and mobility for injury prevention.

### Key journey moment (demo script)
Bloodwork shows low ferritin. The app explains why she's felt flat on long runs, adds iron-rich meals to her plan, softens her next two weeks of training, and schedules a follow-up lab before race month.

### Seed data needed
- 14 days of wearable data: sleep, HRV, resting HR, with worse sleep and lower HRV on travel days
- Strava runs for the last 3 weeks, with a few long runs marked low effort / felt flat
- Calendar: Chicago trip Tue-Thu this week, early mornings mostly free
- Cycle phase for today
- Training plan for the next 3 weeks (includes a tempo run on a Chicago day)
- Labs: one recent panel with ferritin LOW, others in range
- Appointments: no physical in 2+ years (suggested), one past bloodwork visit
- 5 past check-ins showing low energy on heavy work/travel days

---

## Persona 2: Jasmine (`jasmine`), 34, remote IT assistant, pregnant with her second child

Jasmine is 20 weeks pregnant with her second child. Her first is 3 years old. Her family just moved from the city to the suburbs for more space, and she works remotely as an IT assistant on a fairly steady 9-5 schedule. She left behind her OB, primary care doctor and her toddler's pediatrician, so she's rebuilding her whole care team while pregnant. She's tired, her sleep is broken by pregnancy discomfort and a toddler who wakes at night, and her main exercise is walking around her new neighborhood. She wears a Fitbit or Oura ring and uses a pregnancy tracking app.

**Goals:** Healthy pregnancy, better sleep, walk daily, get her new care team set up without anything falling through the cracks.

**Frustrations:** Transferring records is confusing, she doesn't know which local doctors are good or in-network, she's juggling her own and her toddler's appointments, and most fitness and nutrition advice isn't pregnancy-safe.

**How she uses the app:** Laptop during work breaks, phone in the evenings after bedtime. Wants things simple and reassuring, not more to manage.

### What Jasmine needs, by pane
- **Onboarding:** Due date and pregnancy week, prior pregnancy history, recently moved. "Care transition" as main goal alongside sleep and walking.
- **Dashboard:** Pregnancy week, last night's sleep, today's walk goal, care transition checklist ("2 of 4 providers found").
- **Data connections:** Oura or Fitbit, pregnancy app, calendar, upload or request records from previous providers.
- **Appointments:** Find in-network OB, primary care, pediatrician near new address. Prenatal visit schedule by week, upcoming tests, booking around work hours. Holds family appointments for her toddler.
- **Records transfer:** Guided checklist of what to request from old providers (prenatal records, lab results, vaccine history), with status tracking per request.
- **Post-appointment:** Quick notes after each prenatal visit, e.g. "next visit at 24 weeks, glucose screening scheduled."
- **Labs:** Prenatal labs over time (hemoglobin, iron, thyroid, glucose screening) with plain-language explanations and what's next. Always points back to her OB for interpretation.
- **Mood and symptoms:** Sleep quality, energy, mood, swelling, nausea, stress. Gently watches for mood changes during pregnancy and after birth, with an easy way to reach support.
- **Nutrition:** Pregnancy-safe meals, iron- and protein-rich options, hydration reminders, easy family meals.
- **Workouts:** Walking goals by trimester and energy, prenatal stretches, gentle strength. Local walking routes.
- **Sleep:** Sleep trends, wind-down reminders, pregnancy-friendly tips, patterns like "you sleep better on days you walk 30+ minutes."

### Key journey moment (demo script)
Jasmine's records from her old OB haven't arrived, and her first appointment with her new OB is in a week. The app flags the gap, reminds her to follow up with her old office, and shows that her new OB will need her earlier lab results. After the visit, her new care team is fully in place, her glucose screening is booked, and her walking plan is updated for the third trimester.

### Seed data needed
- Pregnancy: week 20, due date, second pregnancy
- 14 days of Oura/Fitbit data: broken sleep, steps from walks, with better sleep on 30+ min walk days
- Care team: OB found (first visit in 7 days), primary care found, pediatrician NOT found, one more provider NOT found ("2 of 4")
- Records transfer: prenatal records from old OB = requested, NOT received (overdue); vaccine history = received; lab results = not requested
- Toddler (age 3) with a pediatric appointment needed
- Labs: earlier prenatal panel at old OB (only available once records arrive), glucose screening upcoming
- 5 past check-ins: low sleep, mild swelling, moderate stress
