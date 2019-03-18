<!-- add-breadcrumbs -->
# Shopify Integration

The Shopify Connector pulls the orders from Shopify and creates Sales Order against them in Dokie.

While creating the sales order if Customer or Item is missing in Dokie the system will create new Customer/Item by pulling respective details from Shopify.

### How to Setup Connector?

#### Create A  Private App in Shopify

1. Click on Apps in menu bar
<img class="screenshot" alt="Menu Section" src="./assets/app_menu.png">

2. Click on **Manage private apps** to create private app
<img class="screenshot" alt="Manage Private Apps" src="./assets/manage_private_apps.png">

3. Fill up the details and create app. The each app has its own API key, Password and Shared secret
<img class="screenshot" alt="App Details" src="./assets/app_details.png">


#### Setting Up Shopify  on Dokie:-
Once you have created a Private App on Shopify, setup App Credentials and other details in Dokie.

1. Select App Type as Private and Fill-up API key, Password and Shared Secret from Shopify's Private App.
<img class="screenshot" alt="Setup Private App Credentials" src="./assets/app_details.png">

2. Setup Customer, Company and Inventory configurations
<img class="screenshot" alt="ERP Configurations" src="./assets/erp_configurations.png">

3. Setup Sync Configurations.
    The system pulls Orders from Shopify and creates Sales Order in Dokie. You can configure Dokie system to capture payment and fulfilments against orders.
<img class="screenshot" alt="Sync Configure" src="./assets/sync_config.png">

4. Setup Tax Mapper.
    Prepare tax and shipping charges mapper for each tax and shipping charge you apply in Shopify
<img class="screenshot" alt="Taxes and Shipping Charges" src="./assets/tax_config.png">


After setting up all the configurations, enable the Shopify sync and save the settings. This will register the API's to Shopify and the system will start Order sync between Shopify and Dokie.

### Note:
The connector won't handle Order cancellation. If you cancelled any order in Shopify then manually you have to cancel respective Sales Order and other documents in Dokie.
