<!-- add-breadcrumbs -->
# Tasks

Project is divided into Tasks. 
In Dooks, you can also create a Task independently.

<img class="screenshot" alt="Task" src="./assets/task.png">

### Status of the Task

A Task can have one of the following statuses - Open, Working, Pending Review, Closed, or Cancelled.

<img class="screenshot" alt="Task - Status" src="./assets/task_status.png">

* By default each new Task created has the status set to 'Open'.

* If a Time Log is made against a task, its status will be set to 'Working'.

### Dependent Task

You can specify a list of dependent tasks under the 'Depends On' section.

<img class="screenshot" alt="Depends On" src="./assets/task_depends_on.png">

* You cannot close the parent task until all dependent tasks are closed.

* If the dependent tasks are delayed and overlap with the expected Start Date of the Parent task, the system will reschedule the parent task.

### Managing Time

Dooks uses [Time Log](/dooks/projects/timesheet/) to track the progress of a Task.
You can create multiple Time Logs against each task.
The Actual Start and End Time along with the costing is updated based on the Time Log.

* To view Time Log made against a Task click on 'Time Logs'

<img class="screenshot" alt="Task - View Time Log" src="./assets/task_view_time_log.png">

<img class="screenshot" alt="Task - Time Log List" src="./assets/task_time_log_list.png">

* You can also create a Time Log directly and link it to the Task.

<img class="screenshot" alt="Task - Link Time Log" src="./assets/task_time_log_link.png">

### Managing Expenses

You can book [Expense Claim](/dooks/human-resources/travel_and_expense_claim/expense-claim.md) against a task.
The system shall update the total amount from expense claims in the costing section.

* To view Expense Claims made against a Task click on 'Expense Claims'

<img class="screenshot" alt="Task - View Expense Claim" src="./assets/task_view_expense_claim.png">

* You can also create a Expense Claims directly and link it to the Task.

<img class="screenshot" alt="Task - Link Expense Claim" src="./assets/task_expense_claim_link.png">

* Total amount of Expense Claims booked against a task is shown under 'Total Expense Claim' in the Task Costing Section

<img class="screenshot" alt="Task - Total Expense Claim" src="./assets/task_total_expense_claim.png">

<div class="embed-container">
    <iframe src="https://www.youtube.com/embed/IxY-rSJsA6U?end=126rel=0" frameborder="0" allow="autoplay; encrypted-media" allowfullscreen></iframe>
</div>

{next}
