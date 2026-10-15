"""Shared, idempotent evidence-based classification overrides."""


def apply_override(post, config):
    override = config.get('overrides', {}).get(post['id'])
    if not override:
        return
    sites = list(override.get('sites', []))
    if not set(sites) <= {s['name'] for s in config['sites']}:
        raise ValueError('Unknown site in classification override')
    category = override.get('category', '사이트별' if sites else '미분류')
    if category not in {'사이트별', '공통', '미분류', '추가 범위'}:
        raise ValueError('Unknown override category')
    evidence = override.get('evidence') or 'sites.json'
    post.update(sites=sites, category=category,
                supplemental_sites=list(override.get('supplemental_sites', [])),
                classification_evidence=[{'site': site, 'field': 'override', 'alias': evidence}
                                         for site in sites or [category]])
