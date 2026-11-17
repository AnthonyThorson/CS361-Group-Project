Scenario: Student books an available slot

When a student views a professor's available office hourse
And they select a sliot
And confirm the booking
Then they should recieve a confirmation message that says it was booked
And said slot should show as booked for other students
And they should recieve a confirmation email with the date, time and office location (or link to online meeting)
And the professor should recieve an email, notifying them of the new appointment, also with the date, time, and whether it is in person or online (if it is online, it includes the link as well)
