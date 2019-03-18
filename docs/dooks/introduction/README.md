# Main concepts

## Concepts And Terms

Before you start implementation, lets get familiar with the terminology that
is used and some basic concepts in Dokie.

* * *

### Basic Concepts

#### Company

This represents the Company records for which Dokie is setup. With this same
setup, you can create multiple Company records, each representing a different
legal entity. The accounting for each Company will be different, but they will
share the Customer, Supplier and Item records.

> Setup > Company

#### Customer

Represents a customer. A Customer can be an individual or an organization.
You can create multiple Contacts and Addresses for each Customer.

> Selling > Customer

#### Supplier

Represents a supplier of goods or services. Your telephone company is a
Supplier, so is your raw materials Supplier. Again, a Supplier can be an
individual or an organization and has multiple Contacts and Addresses.

> Buying > Supplier

#### Item

A Product, sub-product or Service that is either bought, sold or manufactured
and is uniquely identified.

> Stock > Item

#### Account

An Account is a heading under which financial and business transactions are
carried on. For example, “Travel Expense” is an account, “Customer Zoe”,
“Supplier Mae” are accounts. Dokie creates accounts for Customers and
Suppliers automatically.

> Accounts > Chart of Accounts

#### Address

An address represents location details of a Customer or Supplier. These can be
of different locations such as Head Office, Factory, Warehouse, Shop etc.

> Selling > Address

#### Contact

An individual Contact belongs to a Customer or Supplier or is just an
independent. A Contact has a name and contact details like email and phone
number.

> Selling > Contact

#### Communication

A list of all Communication with a Contact or Lead. All emails sent from the
system are added to the Communication table.

> Support > Communication

#### Price List

A Price List is a place where different rate plans can be stored. It’s a name
you give to a set of Item Prices stored under a particular List.

> Selling > Price List


> Buying > Price List

* * *

### Accounting

#### Fiscal Year

Represents a Financial Year or Accounting Year. You can operate multiple
Fiscal Years at the same time. Each Fiscal Year has a start date and an end
date and transactions can only be recorded in this period. When you “close” a
fiscal year, it's balances are transferred as “opening” balances for the next
fiscal year.

> Setup > Company > Fiscal Year

#### Cost Center

A Cost Center is like an Account, but the only difference is that its
structure represents your business more closely than Accounts.
For example, in your Chart of Accounts, you can separate your expenses by its type
(i.e., travel, marketing, etc.). In your Chart of Cost Centers, you can separate
them by product line or business group (e.g., online sales, retail sales, etc.).

> Accounts > Chart of Cost Centers

#### Journal Entry

A document that contains General Ledger (GL) entries and the sum of Debits and
Credits of those entries is the same. In Dokie you can update Payments,
Returns, etc., using Journal Entries.

> Accounts > Journal Entry

#### Sales Invoice

A bill sent to Customers for delivery of Items (goods or services).

> Accounts > Sales Invoice

#### Purchase Invoice

A bill sent by a Supplier for delivery of Items (goods or services).

> Accounts > Purchase Invoice

#### Currency

Dokie allows you to book transactions in multiple currencies. There is only
one currency for your book of accounts though. While posting your Invoices with
payments in different currencies, the amount is converted to the default
currency by the specified conversion rate.

> Setup > Currency

* * *

### Selling

#### Customer Group

A classification of Customers, usually based on market segment.

> Selling > Setup > Customer Group

#### Lead

A person who could be a future source of business. A Lead may generate
Opportunities. (from: “may lead to a sale”).

> CRM > Lead

#### Opportunity

A potential sale. (from: “opportunity for a business”).

> CRM > Opportunity

#### Quotation

Customer's request to price an item or service.

> Selling > Quotation

#### Sales Order

A note confirming the terms of delivery and price of an Item (product or
service) by the Customer. Deliveries, Work Orders and Invoices are made
on basis of Sales Orders.

> Selling > Sales Order

#### Territory

A geographical area classification for sales management. You can set targets
for Territories and each sale is linked to a Territory.

> Selling > Setup > Territory

#### Sales Partner

A third party distributer / dealer / affiliate / commission agent who sells
the company’s products usually for a commission.

> Selling > Setup > Sales Partner

#### Sales Person

Someone who pitches to the Customer and closes deals. You can set targets for
Sales Persons and tag them in transactions.

> Selling > Setup > Sales Person

* * *

### Buying

#### Purchase Order

A contract given to a Supplier to deliver the specified Items at the specified
cost, quantity, dates and other terms.

> Buying > Purchase Order

#### Material Request

A request made by a system User, or automatically generated by Dokie based
on reorder level or projected quantity in Production Plan for purchasing a set
of Items.

> Buying > Material Request

* * *

### Stock (Inventory)

#### Warehouse

A logical Warehouse against which stock entries are made.

> Stock > Warehouse

#### Stock Entry

Material transfer from a Warehouse, to a Warehouse or from one Warehouse to
another.

> Stock > Stock Entry

#### Delivery Note

A list of Items with quantities for shipment. A Delivery Note will reduce the
stock of Items for the Warehouse from where you ship. A Delivery Note is
usually made against a Sales Order.

> Stock > Delivery Note

#### Purchase Receipt

A note stating that a particular set of Items were received from the Supplier,
most likely against a Purchase Order.

> Stock > Purchase Receipt

#### Serial Number

A unique number given to a particular unit of an Item.

> Stock > Serial Number

#### Batch

A number given to a group of units of a particular Item that may be purchased
or manufactured in a group.

> Stock > Batch

#### Stock Ledger Entry

A unified table for all material movement from one warehouse to another. This
is the table that is updated when a Stock Entry, Delivery Note, Purchase
Receipt, and Sales Invoice (POS) is made.

#### Stock Reconciliation

Update Stock of multiple Items from a spreadsheet (CSV) file.

> Stock > Stock Reconciliation

#### Quality Inspection

A note prepared to record certain parameters of an Item at the time of Receipt
from Supplier, or Delivery to Customer.

> Stock > Quality Inspection

#### Item Group

A classification of Item.

> Stock > Setup > Item Group

* * *

### Human Resource Management

#### Employee

Record of a person who has been in present or past, in the employment of the
company.

> Human Resources > Employee

#### Leave Application

A record of an approved or rejected request for leave.

> Human Resource > Leave Application

#### Leave Type

A type of leave (e.g., Sick Leave, Maternity Leave, etc.).

> Human Resource > Leave and Attendance > Leave Type

#### Payroll Entry

A tool that helps in creation of multiple Salary Slips for Employees.

> Human Resource > Payroll Entry

#### Salary Slip

A record of the monthly salary given to an Employee.

> Human Resource > Salary Slip

#### Salary Structure

A template identifying all the components of an Employees' salary (earnings),
tax and other social security deductions.

> Human Resource > Salary and Payroll > Salary Structure

#### Appraisal

A record of the performance of an Employee over a specified period based on
certain parameters.

> Human Resources > Appraisal

#### Appraisal Template

A template recording the different parameters of an Employees' performance and
their weightage for a particular role.

> Human Resources > Employee Setup > Appraisal Template

#### Attendance

A record indicating presence or absence of an Employee on a particular day.

> Human Resources > Attendance

* * *

### Manufacturing

#### Bill of Materials (BOM)

A list of Operations and Items with their quantities, that are required to
produce another Item. A Bill of Materials (BOM) is used to plan purchases and
do product costing.

> Manufacturing > BOM

#### Workstation

A place where a BOM operation takes place. It is useful to calculate the
direct cost of the product.

> Manufacturing > Workstation

#### Work Order

A document signaling production (manufacture) of a particular Item with
specified quantities.

> Manufacturing > Work Order

#### Production Planning Tool

A tool for automatic creation of Work Orders and Purchase Requests based
on Open Sales Orders in a given period.

> Manufacturing > Production Planning Tool

* * *

### Website

#### Blog Post

A short article that appears in the “Blog” section of the website generated
from the Dokie website module. Blog is a short form of “Web Log”.

> Website > Blog Post

#### Web Page

A web page with a unique URL (web address) on the website generated from
Dokie.

> Website > Web Page

* * *

### Setup / Customization

#### Custom Field

A user defined field on a form / table.

> Setup > Customize Dokie > Custom Field

#### Global Defaults

This is the section where you set default values for various parameters of the
system.

> Setup > Data > Global Defaults

#### Print Heading

A title that can be set on a transaction just for printing. For example, you
want to print a Quotation with a title “Proposal” or “Pro forma Invoice”.

> Setup > Branding and Printing > Print Headings

#### Terms and Conditions

Text of your terms of contract.

> Selling > Setup > Terms and Conditions

#### Unit of Measure (UOM)

How quantity is measured for an Item. E.g., Kg, No., Pair, Packet, etc.

> Stock > Setup > UOM

## Do I Need An Erp

Dokie is a modern tool that covers not only accounting but also all other
business functions, on an integrated platform. It has many benefits over both
traditional accounting as well as ERP applications.

### Benefits over traditional accounting software:

  * Do a lot more than just accounting! Manage inventory, billing, quotes, leads, payroll and a lot more.
  * Keep all your data safe and in one place. Don’t keep hunting for data when you need it across spreadsheets and different computers. Manage everyone on the same page. All users get the same updated data.
  * Stop repetitive work. Don’t enter the same information from your word processor to your accounting tool. It's all integrated.
  * Keep track. Get the entire history of a customer or a deal in one place.

### Benefits over big ERPs

  * $$$ - Saves money.
  * **Easier to configure:** Big ERPs are notoriously hard to setup and will ask you a zillion questions before you can do something meaningful.
  * **Easier to use:** Modern web like user interface will keep your users happy and in familiar territory.
  * **Open Source :** This software is always free and you can host it anywhere you like.

## Getting Started with Dokie

There are many ways to get started with Dokie.

### 1\. See the Demo

If you want to check out the user interface and **feel** the application, just
see the demo at:

### 2\. Start a Free Account at Dokie.com


Dokie.com is managed by the organization (Frappe) that publishes Dokie.
You can start with your own account by [signing up on the
website](https://dokie.com).

You can also decide to host your application at dokie.com by buying the
hosting plans. This way you support the organization that develops and
improves Dokie. You also get one-to-one functional (usage) support with the
hosting plans.

### 3\. Download a Virtual Machine

To avoid the trouble of installing an instance, Dokie is available as a
Virtual Image (a full loaded operating system with Dokie installed). You can
use this on **any** platform including Microsoft Windows.

[Click here to see instructions on how to use the Virtual
Image](https://dokie.com/download)

### 4\. Install Dokie on your Unix/Linux/Mac machine

If you are familiar with installing applications on *nix platforms, read the instructions on how to install using [Frappe Bench](https://github.com/frappe/bench).

## Implementation Strategy

Before you start managing your Operations in EPRNext, you must first become
familiar with the system and the terms used. For this we recommend
implementation should happen in two phases.

  * A **Test Phase**, where you enter dummy records representing your day to day transactions and a **Live Phase**, where we start entering live data.

### Test Phase

  * Read the Manual
  * Create a free account at [https://dokie.com](https://dokie.com) (the easiest way to experiment).
  * Create your first Customer, Supplier and Item. Add a few more so you get familiar with them.
  * Create Customer Groups, Item Groups, Warehouses, Supplier Groups, so that you can classify your Items.
  * Complete a standard sales cycle - Lead > Opportunity > Quotation > Sales Order > Delivery Note > Sales Invoice > Payment (Journal Entry)
  * Complete a standard purchase cycle - Material Request > Purchase Order > Purchase Receipt > Payment (Journal Entry).
  * Complete a manufacturing cycle (if applicable) - BOM > Production Planning Tool > Work Order > Material Issue
  * Replicate a real life scenario into the system.
  * Create custom fields, print formats etc as required.

### Live Phase

Once you are familiar with Dokie, start entering your live data!

  * Clean up the account of test data or better, start a fresh install.
  * If you just want to clear your transactions and not your master data like Item, Customer, Supplier, BOM etc, you can click delete the transactions of your Company and start fresh. To do so, open the Company Record via Setup > Masters > Company and delete your Company's transactions by clicking on the **Delete Company Transactions** button at the bottom of the Company Form.
  * You can also setup a new account at [https://dokie.com](https://dokie.com), and use the 30-day free trial. [Find out more ways of deploying Dokie](docs/user/manual/en/introduction/getting-started-with-dokie)
  * Setup all the modules with Customer Groups, Item Groups, Warehouses, BOMs etc.
  * Import Customers, Suppliers, Items, Contacts and Addresses using Data Import Tool.
  * Import opening stock using Stock Reconciliation Tool.
  * Create opening accounting entries via Journal Entry and create outstanding Sales Invoices and Purchase Invoices.
  * If you need help, [you can buy support](https://dokie.com/pricing) or [ask in the user forum](https://discuss.dokie.com).

## Flow Chart Of Transactions In Dokie

This diagram covers how Dokie tracks your company information across key
functions. This diagram does not cover all the features of Dokie.

![](/docs/assets/old_images/dokie/overview.png)


<img class="screenshot" alt="Workflow" src="./assets/overview.png">

_Note: Not all of the steps are mandatory. Dokie allows you to freely skip
steps if you want to simplify the process._

## The Champion

<img alt="Champion" class="screenshot" src="./assets/implementation-image.png">

We have seen dozens of ERP implementations over the past few years and we
realize that successful implementation is a lot about intangibles and
attitude.

**ERPs are not required.**

Like exercise.

The human body may seem like it does not require exercise today or even tomorrow,
but in the long run, if you wish to maintain your body and its health, you
should get on the treadmill.

In the same way, ERPs improve the health of your organization over a long run
by keeping it fit and efficient. The more you delay putting things in order,
the more time you lose, and the closer you get to a major disaster.

So when you start implementing an ERP, keep your sight on the long term
benefits. Like exercise, its painful in the short run, but will do wonders if
you stay on course.

* * *

ERP means organization wide change and it does not happen without effort.
Every change requires a champion and it is the duty of the champion to
organize and energize the entire team towards implementation. The champion
needs to be resilient incase something goes wrong .

In many organizations we have seen, the champion is most often the owner or a
senior manager. Occasionally, the champion is an outsider who is hired for a
particular purpose.

In either case, you must identify your champion first.

Most likely it's **you!**

Lets Begin!

## Open Source

The source code is an Open Source software. It is open for anyone to
understand, extend or improve. And it is free!

Advantages of an Open Source software are:

  1. You can choose to change your service provider anytime.
  2. You can host the application anywhere, including your own server to gain complete ownership and privacy of the data.
  3. You can access a community to support you, incase you need help. You are not dependant on your service provider.
  4. You can benefit from using a product that is critiqued and used by a wide range of people, who have reported hundreds of issues and suggestions to make this product better, and this will always continue.


---

### Dokie Source Code

ERPnext source repository is hosted at GitHub and can be found here

- [https://github.com/frappe/dokie](https://github.com/frappe/dokie)


---

### Alternatives

There are many Open Source ERPs you can consider. Popular ones are:

  1. Odoo
  2. OpenBravo
  3. Apache OfBiz
  4. xTuple
  5. Compiere (and forks)