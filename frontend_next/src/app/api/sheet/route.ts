import { GoogleSpreadsheet } from 'google-spreadsheet';
import { JWT } from 'google-auth-library';

export async function POST(request: Request) {
  try {
    const reqBody = await request.json();

    const serviceAccountAuth = new JWT({
      email: process.env.GOOGLE_SERVICE_ACCOUNT_EMAIL,
      key: process.env.GOOGLE_PRIVATE_KEY,
      scopes: ['https://www.googleapis.com/auth/spreadsheets'],
    });

    const doc = new GoogleSpreadsheet(process.env.SPREADSHEET_ID, serviceAccountAuth);
    await doc.loadInfo();

    const sheet = doc.sheetsByIndex[0];

    // Define a header row explicitamente sem checar se já foi carregada
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
  } catch (error: any) {
    console.error('Erro ao enviar dados para o Google Sheets:', error);
    return new Response(
      JSON.stringify({ result: 'error', error: error.message }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}
