This is the landing page of the Lambda Labs company created in [Next.js](https://nextjs.org).

## Getting Started

This project requires the following environment variables (.env) to be set for capturing leads in the beta signup:

- `GOOGLE_SERVICE_ACCOUNT_EMAIL`: The email address of your Google service account.
- `GOOGLE_PRIVATE_KEY`: The private key associated with your Google service account.
- `SPREADSHEET_ID`: The ID of the Google Spreadsheet you want to access.

These variables are used to authenticate and access a Google Spreadsheet for data storage and retrieval.

First, install the dependencies:

```bash
npm install
# or
yarn install
# or
pnpm install
# or
bun install
```

Then, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.