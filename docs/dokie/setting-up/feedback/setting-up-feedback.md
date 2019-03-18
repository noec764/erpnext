<!-- add-breadcrumbs -->
# Feedback Trigger

You can set up the Feedback Trigger for various documents to get the Feedback from the user.

For this, you will need to setup the Feedback Trigger,

> Setup > Email > Feedback Trigger

### Setting Up Feedback Trigger

To Setup an Feedback:

1. Select which Document Type you want to send feedback request mail.
2. Select the Email Field, This field will be used to get the recipients email id.
3. Set the Subject for feedback request mail.
4. Set the conditions, if all the conditions are met only then the feedback request mail will be sent.
5. Compose the message.

### Setting a Subject
::: v-pre
You can retrieve the data for a particular field by using `doc.[field_name]`. To use it in your subject/message, you have to surround it with `{{ }}`. These are called [Jinja](http://jinja.pocoo.org/) tags. So, for example, to get the name of a document, you use `{{ doc.name }}`. The below example sends an feedback request whenever Issue is Closed with the Subject, "ISS-##### Issue is Resolved"
:::

<img class="screenshot" alt="Setting Subject" src="../assets/feedback/feedback-trigger-subject.png">

### Setting Conditions

Feedback Trigger allows you to set conditions according to the field data in your documents. The feedback request email will be sent on document save only if the all conditions are true For example if you want to trigger the feedback request mail to a customer if an Issue is has been saved as "Closed" as it's status, you put `doc.status == "Closed"` in the conditions textbox. You can also set more complex conditions by combining them.

<img class="screenshot" alt="Setting Condition" src="../assets/feedback/feedback-trigger-condition.png">

### Setting a Message

::: v-pre
You can use both Jinja Tags (`{{ doc.[field_name] }}`) and HTML tags in the message textbox.

	<h3>Your Support Ticket is Resolved</h3>

	<p>Issue {{ doc.name }} Is resolved. Please check and confirm the same.</p>
	<p> Your Feedback is important for us. Please give us your Feedback for {{ doc.name }}</p>
	<p> Please visit the following url for feedback.</p>

	{{ feedback_url }}
:::

---

### Example

1. Setting up Feedback Trigger
    <img class="screenshot" alt="Defining Criteria" src="../assets/feedback/setting-up-feedback-trigger.png">

1. Setting the Recipients and Message
    <img class="screenshot" alt="Set Message" src="../assets/feedback/setting-up-feedback-trigger-message.png">

{next}
