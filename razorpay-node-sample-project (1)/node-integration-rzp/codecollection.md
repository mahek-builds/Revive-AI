**NodeJS PG Integration Video (Codes)**


# Create a New Node JS Project

Let's start by creating a new Node.js project within a folder called razorpay-node-integration.

`mkdir razorpay-node-integration`

`cd razorpay-node-integration`

Within razorpay-node-integration, open your terminal and run `npm init`  to initialize a new project. Follow the prompts to set up the project details.


## Initialize a new Node.js project:

`npm init -y`



## Installing Dependencies
Next, we need to install some essential packages to work with Razorpay. 

Run `npm install express razorpay body-parser` to install Express.js, body parser and Razorpay.


# Step 1: Create an order using Orders API in the server

Let us use Razorpay Orders API to create an order. 

Create an Express server. 
Set up a basic server configuration with routes to handle payment requests.

Create a new file named `app.js` in your project directory. 
This file will serve as the entry point for your application.

```js: Code
const express = require('express');
const Razorpay = require('razorpay');
const bodyParser = require('body-parser');
const path = require('path');
const fs = require('fs');


const app = express();
const port = process.env.PORT || 3000;

app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

// Serve static files
app.use(express.static(path.join(__dirname)));
```


Next we will add the Razorpay API Keys.

```js: Code
// Replace with your Razorpay credentials
const razorpay = new Razorpay({
  key_id: 'rzp_test_Y2wy8t1wD1AFaA',
  key_secret: 'zSqRMpIa2ljBBpkieFYGmfLa',
});
```

Add the following code to extract and store order API response information.

```js: Code
// Function to read data from JSON file
const readData = () => {
 if (fs.existsSync('orders.json')) {
   const data = fs.readFileSync('orders.json');
   return JSON.parse(data);
 }
 return [];
};


// Function to write data to JSON file
const writeData = (data) => {
 fs.writeFileSync('orders.json', JSON.stringify(data, null, 2));
};


// Initialize orders.json if it doesn't exist
if (!fs.existsSync('orders.json')) {
 writeData([]);
}
```

Let us now integrate the orders API.

```js: Code
// Route to handle order creation
app.post('/create-order', async (req, res) => {
  try {
    const { amount, currency, receipt, notes } = req.body;

    const options = {
      amount: amount * 100, // Convert amount to paise
      currency,
      receipt,
      notes,
    };

    const order = await razorpay.orders.create(options);
    
    // Read current orders, add new order, and write back to the file
    const orders = readData();
    orders.push({
      order_id: order.id,
      amount: order.amount,
      currency: order.currency,
      receipt: order.receipt,
      status: 'created',
    });
    writeData(orders);

    res.json(order); // Send order details to frontend, including order ID
  } catch (error) {
    console.error(error);
    res.status(500).send('Error creating order');
  }
});
```

Let us add a route to redirect users to the payment success page.

```js: Code
// Route to serve the success page
app.get('/payment-success', (req, res) => {
  res.sendFile(path.join(__dirname, 'success.html'));
});
```

Now let us start the server!

```js: Code
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});
```


# Step 2: Add Razorpay Checkout Sample Code to your website’s index.html file and pass order id


We'll create a simple HTML page to accept user payment. 
This page will have a pay button that will be used to trigger the payment process.

Create an HTML file as index.html. Next we will add the Razorpay checkout script and parameters.

```html: Code
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Razorpay Payment</title>
</head>
<body>
  <h1>Razorpay Payment Gateway Integration</h1>
  <form id="payment-form">
    <label for="amount">Amount:</label>
    <input type="number" id="amount" name="amount" required>
    <button type="button" onclick="payNow()">Pay Now</button>
  </form>

  <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
  <script>
    async function payNow() {
      const amount = document.getElementById('amount').value;

      // Create order by calling the server endpoint
      const response = await fetch('/create-order', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ amount, currency: 'INR', receipt: 'receipt#1', notes: {} })
      });

      const order = await response.json();

      // Open Razorpay Checkout
      const options = {
        key: 'rzp_test_Y2wy8t1wD1AFaA', // Replace with your Razorpay key_id
        amount: order.amount,
        currency: order.currency,
        name: 'Your Company Name',
        description: 'Test Transaction',
        order_id: order.id, // This is the order_id created in the backend
        callback_url: 'http://localhost:3000/payment-success', // Your success URL
        prefill: {
          name: 'Your Name',
          email: 'your.email@example.com',
          contact: '9999999999'
        },
        theme: {
          color: '#F37254'
        },
      };

      const rzp = new Razorpay(options);
      rzp.open();
    }
  </script>
</body>
</html>
```


# Step 3: Start the Application
Now that you have set up the server and the frontend, you can start your Node.js application. Run the following command in your project directory:

`node app.js`


Visit http://localhost:3000 in your web browser, and you should see the "Pay Now" button. 

# Step 4: Verify Payment Signature
Once the integration goes live, Razorpay sends a callback to this sample app’s server. We'll implement a route to handle this callback, verify the payment, and update the transaction status.


Add the following code in the app.js file.

```js: Code
const { validateWebhookSignature } = require('razorpay/dist/utils/razorpay-utils');


.
.
.

// Route to handle payment verification
app.post('/verify-payment', (req, res) => {
  const { razorpay_order_id, razorpay_payment_id, razorpay_signature } = req.body;

  const secret = razorpay.key_secret;
  const body = razorpay_order_id + '|' + razorpay_payment_id;

  try {
    const isValidSignature = validateWebhookSignature(body, razorpay_signature, secret);
    if (isValidSignature) {
      // Update the order with payment details
      const orders = readData();
      const order = orders.find(o => o.order_id === razorpay_order_id);
      if (order) {
        order.status = 'paid';
        order.payment_id = razorpay_payment_id;
        writeData(orders);
      }
      res.status(200).json({ status: 'ok' });
      console.log("Payment verification successful");
    } else {
      res.status(400).json({ status: 'verification_failed' });
      console.log("Payment verification failed");
    }
  } catch (error) {
    console.error(error);
    res.status(500).json({ status: 'error', message: 'Error verifying payment' });
  }
});
```

Add the following code to the index.html file.

```js: Code
//call signature validate method

      handler: function (response) {
          fetch('/verify-payment', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature
            })
          }).then(res => res.json())
            .then(data => {
              if (data.status === 'ok') {
                window.location.href = '/payment-success';
              } else {
                alert('Payment verification failed');
              }
            }).catch(error => {
              console.error('Error:', error);
              alert('Error verifying payment');
            });
        }
```  


# Step 5: Test the Integration

Let's test the payment integration by making a test payment on the application. 
We'll use the test card details provided by Razorpay for testing purposes. 



# Step 6: Verify Payment Status
You can verify the payment status by checking the Transactions -> Payments section on the Razorpay Dashboard.

1. Log in to the Razorpay Dashboard.
2. Navigate to Transactions -> Payments.
3. Click the Payment id to view and confirm the transaction details.

# Step 7: Go Live
Congratulations! Our payment integration is working smoothly in the test mode. To accept payments in live mode and collect real-world payments, replace the Test API Keys with Live API Keys. 

Ensure the KYC is complete for your account to accept and settle payments as per your Settlement Cycle. 



You've successfully integrated the Razorpay payment gateway with your Node.js stack. You can now accept payments securely on your Node.js web application. 

If you have any issues or questions, refer to the Razorpay documentation or leave a comment below. Happy coding!
