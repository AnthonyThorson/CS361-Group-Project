Scenario: Student books an available slot

When a student views a professor's available office hourse
And they select a sliot
And confirm the booking
Then they should recieve a confirmation message that says it was booked
And said slot should show as booked for other students
And they should recieve a confirmation email with the date, time and office location (or link to online meeting)
And the professor should recieve an email, notifying them of the new appointment, also with the date, time, and whether it is in person or online (if it is online, it includes the link as well)


Scenario: Student cancels a booking

Given a student has booked a slot
When they cancel the appointment
Then they should be informed that it's been cancelled
And the slot should become available
And the professor should be notified of the cancellation
