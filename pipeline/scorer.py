CONCRETE_THEMES = {'industrial tech', 'energy transition', 'supply chain and logistics', 'vertical software'}


def assign_status_and_owner(lead, config):
    """
    Apply the scoring matrix and assign status + owner.
    Modifies lead in place. Returns lead.
    """
    theme = (lead.get('investmentTheme') or '').strip().lower()
    is_concrete     = theme in CONCRETE_THEMES
    is_opportunistic = theme == 'opportunistic'
    is_excluded     = theme == 'excluded'

    prio   = lead.get('prioGeo', False)
    second = lead.get('secondPrioGeo', False)
    right  = lead.get('rightStage', False)

    if is_excluded or not right or (not prio and not second):
        lead['status'] = 'No fit'
        lead['owner']  = None
    elif prio and right and is_concrete:
        lead['status'] = 'High priority'
    elif second and right and is_concrete:
        lead['status'] = 'High fit'
    elif prio and right and is_opportunistic:
        lead['status'] = 'Moderate fit'
    elif second and right and is_opportunistic:
        lead['status'] = 'Low fit'
    else:
        lead['status'] = 'No fit'
        lead['owner']  = None

    # Assign owner only for non-No-fit leads
    if lead['status'] != 'No fit':
        country_key = (lead.get('country') or '').strip().lower()
        lead['owner'] = config.get('owner_map', {}).get(country_key)

    return lead
