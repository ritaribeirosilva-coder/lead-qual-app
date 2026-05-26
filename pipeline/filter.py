def derive_stage(lead, config):
    """Derive investmentStage for Sifted leads that lack a named round."""
    thresholds = config['round_size_thresholds']
    if lead.get('roundDisclosed'):
        return lead['roundDisclosed']
    elif lead.get('siftedStage'):
        return lead['siftedStage']
    elif 0 < lead.get('dealSize', 0) <= thresholds['pre_seed_max']:
        return 'Pre-seed'
    elif thresholds['pre_seed_max'] < lead.get('dealSize', 0) <= thresholds['seed_max']:
        return 'Seed'
    else:
        return 'undefined'


def apply_filter(leads, config):
    """
    Apply geo + stage filter to a list of normalized leads.

    Returns:
        {
            'qualifiable': [...],   # leads that passed
            'no_fit': [...]         # leads that failed
        }
    """
    prio_geo_lower      = [g.lower() for g in config.get('prio_geo', [])]
    second_prio_lower   = [g.lower() for g in config.get('second_prio_geo', [])]
    right_stages_lower  = [s.lower() for s in config.get('right_stages', [])]

    qualifiable = []
    no_fit = []

    for lead in leads:
        # Derive stage for Sifted leads
        if lead.get('source') == 'Sifted' and not lead.get('investmentStage'):
            lead['investmentStage'] = derive_stage(lead, config)

        country = (lead.get('country') or '').strip().lower()
        stage   = (lead.get('investmentStage') or '').strip().lower()

        prio_geo       = country in prio_geo_lower
        second_prio_geo = country in second_prio_lower
        right_stage    = stage in right_stages_lower

        lead['prioGeo']       = prio_geo
        lead['secondPrioGeo'] = second_prio_geo
        lead['rightStage']    = right_stage

        is_no_fit = not right_stage or (not prio_geo and not second_prio_geo)

        if is_no_fit:
            lead['status']             = 'No fit'
            lead['owner']              = None
            lead['investmentTheme']    = ''
            lead['themeJustification'] = ''
            lead['whyUs']              = ''
            no_fit.append(lead)
        else:
            qualifiable.append(lead)

    return {'qualifiable': qualifiable, 'no_fit': no_fit}
