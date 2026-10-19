import osmium, json, sys
out = []
for path in sys.argv[1:]:
    region = path.split('/')[-1].split('.')[0]
    fp = osmium.FileProcessor(path).with_filter(osmium.filter.KeyFilter('amenity'))
    for o in fp:
        t = o.tags
        if t.get('amenity') != 'restaurant': continue
        web = t.get('website') or t.get('contact:website') or t.get('url')
        if not web or not t.get('name'): continue
        out.append({
            'osm': f"{o.type_str()}{o.id}", 'region': region, 'name': t.get('name'),
            'cuisine': t.get('cuisine',''), 'website': web,
            'menu_tag': t.get('website:menu',''),
            'street': (t.get('addr:street','')+' '+t.get('addr:housenumber','')).strip(),
            'postcode': t.get('addr:postcode',''), 'city': t.get('addr:city',''),
            'phone': t.get('phone') or t.get('contact:phone',''),
            'email': t.get('email') or t.get('contact:email',''),
        })
json.dump(out, open(sys.stdout.fileno(),'w'), ensure_ascii=False)
