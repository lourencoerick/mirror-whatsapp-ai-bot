from app.models.account import AccountPlanTierEnum  # Importe seu Enum

STRIPE_PRODUCT_TO_PLAN_TIER = {
    "prod_SMPv4MdWl6hBBC": AccountPlanTierEnum.BASIC.value,  # Exemplo de ID de produto Stripe para o plano Básico
    "prod_SN3qNHRMF7W8FR": AccountPlanTierEnum.PRO.value,  # Exemplo de ID de produto Stripe para o plano Pro
    "prod_SLYFjJMKBp22Xz": AccountPlanTierEnum.PRO.value,  # Pro na nova conta
    "prod_SNE188adsMk4vp": AccountPlanTierEnum.ENTERPRISE.value,  # Exemplo de ID de produto Stripe para o plano Enterprise
    # Adicione seus IDs de produto de PRODUÇÃO aqui também, ou use variáveis de ambiente
    "prod_BASIC_XYZ_live": AccountPlanTierEnum.BASIC.value,
    "prod_PRO_ABC_live": AccountPlanTierEnum.PRO.value,
    "prod_ENT_123_live": AccountPlanTierEnum.ENTERPRISE.value,
}
