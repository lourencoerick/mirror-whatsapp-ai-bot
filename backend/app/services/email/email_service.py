# backend/app/services/email_service.py
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, From, To, Subject, Content, HtmlContent
from fastapi import HTTPException, status
from loguru import logger

from app.config import get_settings
from app.api.schemas.beta_tester import BetaTesterCreate  # Para tipar o payload


settings = get_settings()


class EmailService:
    def __init__(self):
        self.sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        self.from_email = From(
            email=settings.EMAILS_FROM_EMAIL, name=settings.EMAILS_FROM_NAME
        )

    async def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        if (
            not settings.SENDGRID_API_KEY
            or settings.SENDGRID_API_KEY == "YOUR_SENDGRID_API_KEY_HERE"
        ):
            logger.error("SendGrid API Key not configured. Email not sent.")
            # Em um ambiente de desenvolvimento, você pode não querer que isso seja um erro fatal.
            # Em produção, isso DEVE ser um erro.
            # Por agora, vamos apenas logar e retornar False.
            return False

        message = Mail(
            from_email=self.from_email,
            to_emails=To(to_email),
            subject=Subject(subject),
            html_content=HtmlContent(html_content),
        )
        try:
            response = self.sg.send(message)
            logger.info(
                f"Email sent to {to_email}, subject: '{subject}', status code: {response.status_code}"
            )
            if response.status_code >= 200 and response.status_code < 300:
                return True
            else:
                logger.error(
                    f"Failed to send email. Status: {response.status_code}, Body: {response.body}"
                )
                return False
        except Exception as e:
            logger.exception(f"Error sending email to {to_email}: {e}")
            return False

    async def send_beta_request_confirmation(self, user_email: str, user_name: str):
        subject = "Confirmação: Solicitação de Acesso Beta Recebida!"
        html_content = f"""
        <p>Olá {user_name or 'Usuário'},</p>
        <p>Recebemos sua solicitação de acesso ao programa beta da nossa plataforma de vendas via WhatsApp!</p>
        <p>Nossa equipe analisará sua aplicação e entraremos em contato em breve com os próximos passos.</p>
        <p>Você pode verificar o status da sua solicitação a qualquer momento aqui: <a href="{settings.FRONTEND_URL}/beta/status">Verificar Status</a>.</p>
        <p>Obrigado pelo seu interesse!</p>
        <p>Atenciosamente,<br/>Equipe {settings.APP_NAME}</p>
        """
        await self.send_email(user_email, subject, html_content)

    async def send_beta_request_admin_notification(
        self, applicant_email: str, applicant_name: str, details: BetaTesterCreate
    ):
        subject = f"Nova Solicitação de Acesso Beta: {applicant_email}"
        admin_beta_requests_url = f"{settings.FRONTEND_URL}/admin/beta-requests"

        details_html = "<ul>"
        details_html += f"<li><strong>Nome de Contato:</strong> {details.contact_name or applicant_name}</li>"
        details_html += f"<li><strong>Email:</strong> {applicant_email}</li>"
        details_html += (
            f"<li><strong>Empresa:</strong> {details.company_name or 'N/A'}</li>"
        )
        details_html += (
            f"<li><strong>Website:</strong> {details.company_website or 'N/A'}</li>"
        )
        details_html += f"<li><strong>Descrição do Negócio:</strong> {details.business_description or 'N/A'}</li>"
        details_html += f"<li><strong>Objetivo com o Beta:</strong> {details.beta_goal or 'N/A'}</li>"
        details_html += "</ul>"

        html_content = f"""
        <p>Olá Administrador,</p>
        <p>Uma nova solicitação de acesso ao programa beta foi recebida:</p>
        {details_html}
        <p>Para revisar e aprovar/negar esta solicitação, acesse o painel de administração:</p>
        <p><a href="{admin_beta_requests_url}">Gerenciar Solicitações Beta</a></p>
        <p>Atenciosamente,<br/>Sistema {settings.APP_NAME}</p>
        """
        if (
            settings.ADMIN_EMAIL_NOTIFICATIONS
            and settings.ADMIN_EMAIL_NOTIFICATIONS != "admin@example.com"
        ):
            await self.send_email(
                settings.ADMIN_EMAIL_NOTIFICATIONS, subject, html_content
            )
        else:
            logger.warning(
                "ADMIN_EMAIL_NOTIFICATIONS not configured. Admin notification email for beta request not sent."
            )

    async def send_beta_approval_email(self, user_email: str, user_name: str):
        subject = "Parabéns! Sua Solicitação Beta Foi Aprovada!"
        beta_status_url = f"{settings.FRONTEND_URL}/beta/status"
        html_content = f"""
        <p>Olá {user_name or 'Usuário'},</p>
        <p>Temos ótimas notícias! Sua solicitação de acesso ao programa beta da nossa plataforma de vendas via WhatsApp foi APROVADA.</p>
        <p>Você já pode acessar a plataforma e começar a explorar os recursos disponíveis para participantes do programa beta.</p>
        <p>Clique aqui para começar: <a href="{beta_status_url}">Acessar Plataforma Beta</a></p>
        <p>Se tiver qualquer dúvida ou precisar de ajuda para começar, não hesite em nos contatar.</p>
        <p>Estamos ansiosos para ter você conosco!</p>
        <p>Atenciosamente,<br/>Equipe {settings.APP_NAME}</p>
        """
        await self.send_email(user_email, subject, html_content)

    async def send_beta_denial_email(self, user_email: str, user_name: str):
        subject = "Atualização Sobre Sua Solicitação de Acesso Beta"
        html_content = f"""
        <p>Olá {user_name or 'Usuário'},</p>
        <p>Agradecemos seu interesse em nosso programa beta. Após uma análise cuidadosa, decidimos não prosseguir com sua aplicação neste momento.</p>
        <p>Estamos constantemente evoluindo e esperamos poder colaborar com você no futuro.</p>
        <p>Atenciosamente,<br/>Equipe {settings.APP_NAME}</p>
        """
        await self.send_email(user_email, subject, html_content)


# Instância global do serviço para fácil importação (opcional, mas comum)
email_service = EmailService()
