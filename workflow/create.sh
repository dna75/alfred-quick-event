#!/bin/bash
# Creates the event in Calendar. Argument: JSON produced by parse.py. Prints a short message for Alfred.
J="$1"
field() { /usr/bin/python3 -c 'import sys,json; d=json.loads(sys.argv[1]); v=d.get(sys.argv[2],""); print("true" if v is True else ("false" if v is False else v))' "$J" "$1"; }
TITLE=$(field title); START=$(field start); END=$(field end); ALLDAY=$(field all_day)
CAL=$(field calendar); PLACE=$(field place); OPEN=$(field open)

RES=$(osascript - "$TITLE" "$START" "$END" "$ALLDAY" "$CAL" "$PLACE" <<'AS' 2>&1
on mkdate(s)
  -- s = "YYYY-MM-DD HH:MM"
  set d to current date
  set day of d to 1
  set year of d to (text 1 thru 4 of s) as integer
  set month of d to (text 6 thru 7 of s) as integer
  set day of d to (text 9 thru 10 of s) as integer
  set time of d to ((text 12 thru 13 of s) as integer) * 3600 + ((text 15 thru 16 of s) as integer) * 60
  return d
end mkdate
on run argv
  set theTitle to item 1 of argv
  set startDate to my mkdate(item 2 of argv)
  set endDate to my mkdate(item 3 of argv)
  set isAllDay to (item 4 of argv) is "true"
  set calName to item 5 of argv
  set loc to item 6 of argv
  tell application "Calendar"
    tell calendar calName
      set ev to make new event with properties {summary:theTitle, start date:startDate, end date:endDate, allday event:isAllDay}
      if loc is not "" then set location of ev to loc
    end tell
  end tell
  return "ok"
end run
AS
)
if [ "$RES" != "ok" ]; then echo "Failed: $RES"; exit 0; fi
[ "$OPEN" = "true" ] && open -a Calendar
echo "$TITLE · $CAL"
