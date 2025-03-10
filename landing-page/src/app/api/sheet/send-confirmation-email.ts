import dotenv from 'dotenv';
dotenv.config();

import sgMail from '@sendgrid/mail';

// Ensure the SendGrid API key is defined
if (!process.env.SENDGRID_API_KEY) {
  throw new Error("SENDGRID_API_KEY is not defined.");
}

// Set the SendGrid API key for authentication
sgMail.setApiKey(process.env.SENDGRID_API_KEY);

// Interface defining the data needed for the confirmation email
interface ConfirmationEmailData {
  to: string;        // Recipient's email address
  first_name: string; // Dynamic field: recipient's first name
  // You can add more dynamic fields here as needed
}

/**
 * Sends a confirmation email using SendGrid dynamic templates.
 *
 * @param data - An object containing the recipient's email and dynamic template data.
 * @returns A promise that resolves when the email is sent successfully.
 */
export async function sendConfirmationEmail(data: ConfirmationEmailData): Promise<void> {
  // Define the email message using a dynamic template
  const msg = {
    to: data.to, // Recipient's email address
    from: {
      email: 'tecnologia@lambdalabs.com.br', // Verified sender email address
      name: 'Lambda Labs'                     // Sender's name
    },
    templateId: 'd-b9ce10b1645b4d4fa97126bee79d95c3', // Replace with your actual dynamic template ID
    dynamicTemplateData: {
      first_name: data.first_name, // Dynamic field for the template
      // Add additional dynamic fields as required by your template
    },
  };

  try {
    // Attempt to send the email
    await sgMail.send(msg);
    console.log('Email sent successfully.');
  } catch (error: unknown) {
    // Log and rethrow any errors encou
    console.error('Error sending email:', error);
    throw error;
  }
}