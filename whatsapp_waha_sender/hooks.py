def create_access_rights(env):
    """Create access rights for this module's models (post-install).

    Odoo 19 does not reliably expose the ``model_<name>`` external id to the
    access-rights CSV loader at data-load time, so we create the ACLs here,
    after the models are fully registered.
    """
    models = [
        'waha.account',
        'waha.template',
        'waha.message',
        'waha.composer',
        'waha.mass_composer',
        'waha.chat.message',
    ]
    group = env.ref('base.group_user', raise_if_not_found=False)
    if not group:
        return
    for model_name in models:
        model = env['ir.model'].search([('model', '=', model_name)], limit=1)
        if not model:
            continue
        if env['ir.model.access'].search_count([
            ('model_id', '=', model.id),
            ('group_id', '=', group.id),
        ]):
            continue
        env['ir.model.access'].create({
            'name': 'WAHA: %s' % model_name,
            'model_id': model.id,
            'group_id': group.id,
            'perm_read': True,
            'perm_write': True,
            'perm_create': True,
            'perm_unlink': True,
        })
