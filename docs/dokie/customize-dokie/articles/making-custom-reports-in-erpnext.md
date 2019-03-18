<!-- add-breadcrumbs -->
#Reports in Dokie

There are three kind of reports in Dokie.

###1. Report Builder

Report Builder is an in-built report customization tool in Dokie. This allows you to define specific fields of the form which shall be added in the report. Also you can set required filters, sorting and give preferred name to report.

<div class="embed-container">
    <iframe src="https://www.youtube.com/embed/TxJGUNarcQs?rel=0" frameborder="0" allow="autoplay; encrypted-media" allowfullscreen>
    </iframe>
</div>

### 2. Query Report

Query Report is written in SQL which pull values from account's database and fetch in the report. Though SQL queries can be written from front end, like HTML, it's restricted for dokie.com cloud users. Because it will allow users with no access to specific report to query data directly from the database.

Check Purchase Order Item to be Received report in Stock module for example of Query report. Click [here](/framework/reports-and-printing/how-to-make-query-report.md) to learn how to create Query Report.

### 3. Script Report

Script Reports are written in Python and stored on server side. These are complex reports which involves logic and calculation. Since these reports are written on server side, customizing it from hosted account is not possible.

Check Financial Analytics report in Accounts module for example of Script Report. Click [here](/framework/reports-and-printing/how-to-make-script-reports.md) to learn how to create Script Report.

{next}

<!-- markdown -->
