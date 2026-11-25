# BSIT Event Organizer System v0.33

Django project with student, organizer, and administrator dashboards.

The v0.30 navy background palette and gradients are restored, including the original grid and orbit decoration on the landing page. The dashboards fill the full viewport without an outer frame. The header, sidebar, and phone bottom navigation occupy separate areas. Only the main content pane scrolls, keeping cards and tables clear of the navigation. The QR scan area stays black and white.

Styles and scripts receive content-based version URLs so upgrades load matching files. Explicit grid areas keep the header, sidebar, and page content in their own positions.

The student, organizer, and administrator sidebars show the application name as plain text and a collapse button at the top. The sidebar fills the left edge from top to bottom, and the account bar fills the available width on the right. Collapse the sidebar to icons or expand it again with its own menu button. The application name hides in the compact sidebar. Each account's choice is remembered on that browser. Profile settings, event details, and attendance pages keep the same sidebar.

On phones and tablets, the bottom navigation stays available with or without JavaScript. The top bar also has an opener for the sidebar. Inside the drawer, the button inside the sidebar closes navigation. The shaded area and Escape also close it. Keyboard focus stays in the open menu. Without JavaScript, the existing bottom tabs remain available.

The uploaded image logo has been removed from pages, sidebars, and the browser tab. This v0.33 release retains the latest application features and database.

## Run locally on Windows

Open PowerShell in the extracted project folder that contains `manage.py`.

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open [BSIT Events](http://127.0.0.1:8000/) for student and organizer sign-in.

On macOS or Linux, use `python3 -m venv venv` and `source venv/bin/activate` for the first two commands.

This ZIP includes the existing SQLite database and administrator account. Use your existing sign-in credentials. For a fresh installation with an empty database, run `python manage.py createsuperuser` after applying migrations.

If you have newer records in your running installation, back it up and copy its current `db.sqlite3`, `media/` folder, and `.env` next to the new `manage.py` before applying migrations. This keeps your latest accounts, events, uploads, Gmail settings, and the signing key used for sessions and QR validation.

## Administrator workflow

Open [Administrator dashboard](http://127.0.0.1:8000/bsiteventsysadmin/). Signed-out visitors are sent to its login page. Use your existing superuser or administrator account. The address stays the same when the signing key changes.

- **Accounts** lets administrators create student and organizer accounts, edit names and email addresses, and activate or deactivate access. For students, use the School ID as the username.
- A Django superuser can choose **Administrator** under **Accounts → Create account**. The new administrator signs in at the direct admin address.
- Open an account and choose **Delete account** to review the impact before confirming permanent deletion. Student attendance records and stamps are deleted with the student account. Deleting an organizer clears their event assignments. Account deletions appear in **Activity log**.
- **Set temporary password** sets a new password and can require the account holder to replace it at their next sign-in. **Send reset email** sends a link to the account's registered address. Existing passwords are never displayed.
- **Events** shows the schedule, organizer assignments, and event details. Status follows the start and end schedule in Manila. For an overnight event, leave **End date** blank and set an end time earlier than the start time. Completed events are view-only. Administrators can cancel or delete events that are still editable.
- **Create event** places map search and media beside the schedule on desktop. Choose the organizer under **Event details**.
- **Attendance** shows each event's time-in and time-out records. Under **Add record**, choose **Time In**, **Time Out**, or **Excused Time Out**. For either checkout type, leave **Time In** blank to use the student's saved time for that day. Use **Correct** on an existing row to edit its times or change the Time Out type. The activity log records the reason and changes. Completed attendance awards the event’s stamps. Removing either time removes that award.
- **Export Excel** downloads a native `.xlsx` workbook. Organizers can also export attendance for their own events.
- **Activity log** records account changes, password reset actions, event changes, scans, and manual attendance corrections.

The portal accepts Django superusers and active users with an **Administrator** profile. The built-in [Django admin](http://127.0.0.1:8000/bsiteventsysadmin/django/) remains available to staff with its assigned permissions.

## Student and organizer workflow

Students register and sign in with their School ID. The desktop workspace puts upcoming events and a QR preview side by side in **Overview**, with the ten-slot stamp card and event history below. The sidebar opens **My QR**, **Stamps**, **Event history**, and **Profile**. **My QR** displays a larger rotating code for scanning. Event details show the program schedule, stamp award, and venue. For attendance times, choose **View days** or **View scans** in event history.

The **Current Time In** section on the student dashboard shows the event, venue, and recorded time for each current check-in. The **In** badge appears on the student's event card, event details, and the active event on **My QR** after Time In for that scheduled day. The entry and badge clear after Time Out. Open screens check for scan updates about once a second.

The personalized **My QR** card shows the student's photo or initial, name, School ID, program, and year/section. Its signed code still changes automatically every 25 seconds. The code's scan area stays clear, and the countdown follows the server even if the student's device clock is wrong.

The assigned organizer scans the QR, then reviews the student's photo, name, School ID, and academic details in a confirmation popup. Compare these with the person in front of you. Choose **Confirm Time In**, **Confirm Time Out**, or **Confirm Excused Time Out** to save the selected action. **Not the same person**, Cancel, and Escape save no attendance. If the photo is missing or cannot load, compare the student's school ID before confirming.

A review lasts up to 60 seconds and can finish while the student's QR continues to change. Confirmation keeps the original scan time and attendance day. A changed student profile, event schedule, or attendance record requires a fresh scan. Expired, cancelled, reused, or session-mismatched confirmations cannot save attendance. Upload or update the student photo under **Profile settings**.

Phones and tablets up to 1024 CSS pixels wide use the slide-out sidebar in the student, organizer, and administrator workspaces. Each role keeps its own links and active page. Open account settings from the profile avatar at the top or the sidebar profile link. On phones, the student **Overview** shows upcoming events and stamp progress, with the full QR, stamp card, and attendance history in their own pages.

**Event history** lists all completed events, with up to twenty per page and Previous/Next controls. The overview and stamp pages keep a short recent-history preview. When several events are running, **My QR** prioritizes the event where the student is checked in. A stalled QR image request times out and retries automatically.

The organizer workspace has an **Overview** with attendance charts and end-time reminders, a **Create event** form with map search and media beside the schedule, a **My events** list, and a **Notifications** inbox. **My events** shows pending checkouts by attendance day, with links that open the scanner for that day. The organizer can narrow the Overview charts to one event using **Filter** and mark their inbox as read from **Notifications**.

For a multi-day program, fill in **End date** and set **Stamps per student** when creating or editing the event. The same start and end times apply on each scheduled date. For overnight sessions, the attendance day is the date the session starts, and the end date is the final morning. Open the scanner each day to record a separate Time In and Time Out per student.

The configured award is issued once the student has both scans on every scheduled day. A three-day program set to one stamp gives one stamp after all three days are complete. The default is one stamp, and zero skips the award. Changing the number applies to future awards. Existing scans are kept on their original attendance dates during the update, and previously issued awards are preserved.

Attendance lists can be filtered by day and show how many days each student completed. The Excel export and student event history also include daily records. Select an earlier attendance day in the scanner or from the attendance list to finish its pending Time Outs.

In the last five minutes, the organizer dashboard and scanner show an **Extend end time** reminder. The organizer can save a later end time before the event completes. The reminder is also saved in **Notifications**.

**Time Out** opens automatically five minutes before each session ends, or at the start for a shorter session. For earlier Time Out, an administrator opens the event in the admin portal, chooses **Approve early Time Out**, and confirms their own password. Approval is limited to the active session for up to five minutes. Changes to the schedule clear the approval.

If a checked-in student needs to leave during the event, the assigned organizer can choose **Excused Time Out** and scan that student's QR. This records their actual departure time and shows **Excused** on the attendance lists, the Excel export, and the student's event history. An excused checkout counts toward completion for that day.

Time In closes at the end of each session. The event becomes **Completed** at its final scheduled end. The assigned organizer can keep scanning **Time Out** for students who already timed in for the selected day. If the scanner was closed, select **Finish Time Out** from My Events, the event details, or the attendance list. The scanner shows how many checkouts are pending for the selected day.

The scanner reviews one student at a time and resumes scanning when the current review is confirmed or cancelled. A visible attendance list refreshes after a confirmed save. A scanner in another tab of the same browser can trigger an immediate refresh, and other devices check for updates about once a second.

Open dashboards and scanners update from the schedule. To also save statuses and generate reminders while everyone is signed out, schedule `python manage.py update_event_timing` every minute in your hosting environment.

When creating or editing an event, expand **Map location**, search for a place or address, and select a result to set the pin. Search uses [Photon](https://photon.komoot.io/) and requires an internet connection. You can also click the map or select **Use current location**, which asks the browser for location permission. Students can open the venue in Google Maps from the dashboard, and event details show the saved pin.

New organizer accounts and accounts assigned a temporary password with a required change see a password-change dialog before the dashboard becomes available. Students and organizers can open their profile to change their password or view notifications.

**Attendance Analytics** appears below the summary cards on Admin Overview and the Organizer Dashboard. Administrators can filter all events, and organizers can filter events they own. The completion rate uses attendance records with both times as a share of records with a time-in.

## Email and deployment

Use a different email address for each account. If accounts created before the update share an address, assign each its own email in **Accounts** so password recovery works.

New passwords must contain 8–16 characters and meet the Fair rating or better. Common passwords, predictable patterns, passwords based on account details, and reuse of the current password are rejected. The strength meter, confirmation feedback, and show/hide controls appear on registration, password changes, resets, first-login setup, and administrator password forms. Whitespace is preserved within the length limit. These rules apply to new passwords; existing credentials continue to work, including passwords longer than sixteen characters.

Run `python -m pip install -r requirements.txt` after updating so the password checker is installed in the same Python environment used by `manage.py`. Missing dependencies now produce an installation hint; password changes remain blocked until the checker is available, and settings and migrations can still load. The browser's estimator is included in the static files and does not send passwords to an external strength-checking service. Django validates the submitted password before saving its hash.

### Send password-reset links with Gmail

1. Enable 2-Step Verification on the Google account that will send the messages. Generate an app password named `BSIT Events`. [Google App Passwords](https://myaccount.google.com/apppasswords)
2. Edit `.env` next to `manage.py`. If you need to create it, copy `.env.example` to `.env`. Set `EMAIL_HOST_USER` to the sender's full Gmail address and `EMAIL_HOST_PASSWORD` to the generated app password. The app defaults to `smtp.gmail.com` on port `587` with TLS. Keep `.env` private.
3. Run `python -m pip install -r requirements.txt` in your app's virtual environment, then restart Django. On PythonAnywhere, put `.env` next to the deployed `manage.py`, set `PASSWORD_RESET_ORIGIN` to your site's HTTPS address, and use **Web → Reload**.
4. Open **Reset password** from the sign-in panel and enter the email saved on your BSIT Events account. The link goes to that address. The Gmail address in `.env` is the sender.

If the email is missing, run this command from the same project folder and environment as the website. It checks the SMTP login and the reset link origin.

```shell
python manage.py check_reset_email
```

After that check passes, send a test message to an inbox you can check with `python manage.py sendtestemail recipient@example.com`. Use the recipient's saved BSIT Events email when requesting the real reset link. SMTP settings supplied by the server environment take precedence over `.env`. If Gmail sender credentials are missing, the reset form displays an email delivery error.

If the email arrives but its link opens the wrong address, set `PASSWORD_RESET_ORIGIN` to the address where the app is running, restart the app, and request a fresh link. A `127.0.0.1` or `localhost` link is for the computer running Django. For a hosted app, use its public HTTPS address. Production reset links default to HTTPS when `PASSWORD_RESET_ORIGIN` is unset.

`DEFAULT_FROM_EMAIL` is optional for Gmail because the app uses the authenticated Gmail address. Account resets and attendance corrections also appear in the affected account's Notifications page.

For a public deployment, set `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY`, and `DJANGO_ALLOWED_HOSTS`. Run `python manage.py collectstatic` and configure the host to serve static files and uploaded media. Use HTTPS for browser camera access. The camera scanner loads `html5-qrcode` from its CDN.

## Run regression checks

Run `python manage.py test` to check rotating QR codes, organizer identity confirmation, expiry and cancellation, daily attendance and stamp awards, password validation and recovery, existing-credential access, student history pagination, and shared dashboard navigation. Django creates a separate test database and leaves the included database unchanged.
