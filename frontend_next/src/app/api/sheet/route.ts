import { GoogleSpreadsheet } from 'google-spreadsheet';
import { JWT } from 'google-auth-library';

export async function POST(request: Request) {
  try {
    const reqBody = await request.json();

    const spreadsheetId = process.env.SPREADSHEET_ID;
    const serviceAccountEmail = process.env.GOOGLE_SERVICE_ACCOUNT_EMAIL;
    const privateKey = process.env.GOOGLE_PRIVATE_KEY;

    if (!spreadsheetId || !serviceAccountEmail || !privateKey) {
      throw new Error("Define the necessary env vars: SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_EMAIL, GOOGLE_PRIVATE_KEY");
    }

    const serviceAccountAuth = new JWT({
      email: serviceAccountEmail,
      key: privateKey,
      scopes: ['https://www.googleapis.com/auth/spreadsheets'],
    });

    const doc = new GoogleSpreadsheet(spreadsheetId, serviceAccountAuth);
    await doc.loadInfo();

    const sheet = doc.sheetsByIndex[0];
    await sheet.setHeaderRow(["name", "email", "timestamp"]);

    const { name, email } = reqBody;

    await sheet.addRow({
      name,
      email,
      timestamp: new Date().toISOString(),
    });

    return new Response(
      JSON.stringify({ result: 'success' }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  } catch (error: Error | unknown) {
    console.error('Error to try sending the data to the google sheets:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    
    return new Response(
      JSON.stringify({ result: 'error', error: errorMessage }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

