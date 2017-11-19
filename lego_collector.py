import re
import glob
import csv
import urllib.request
import lxml.html as lh


def get_sets_from_year(setsfile):
    with open(setsfile) as sf:
        return [(int(line[1]), int(line[2])) for line in csv.reader(sf)
                if (re.match('[0-9]+', line[1])
                    and re.match('[0-9]+', line[2])
                    and 'Minifigures' not in line[3])]


def parse_infobox(el_list):
    infobox = dict()
    key = ''
    values = []
    for el in el_list[1:-1]:
        if el.tag == 'dt':
            if (key not in ['', 'Current value', 'Price per piece',
                            'Barcodes', 'Notes', 'LEGO item numbers']
                    and values != []):
                infobox[key] = ','.join(values)
            key = el.text
            values = []
        elif el.tag == 'dd':
            if (key in ['Theme', 'Subtheme', 'Year released', 'Pieces', 'Minifigs']
                and el.xpath('a') != []):
                values.append(el.xpath('a')[0].text)
            elif key == 'Tags' and len(el.xpath('span/a')) >= 0:
                for a in el.xpath('span/a'):
                    values.append(a.text)
            else:
                values.append(el.text)
    return infobox


def parse_price_guide(text):
    pat = re.compile(
        '((?:January|February|March|April|May|June|July|August|September|October|November|December) (?:[0-9]{4}))')
    split_text = re.split(pat, re.sub('\s+', ' ', text))
    month_label_positions = [i for i, v in enumerate(split_text)
                             if re.match(pat, v)]

    def split_summary_fields(fields_text):
        pat = re.compile(
            '(?:([\sa-zA-Z]+):(?:[A-Z]+\s\$)?([.0-9]+)\s?)')
        matches = list(filter(None, re.split(pat, fields_text)))
        return dict(zip(matches[0::2], matches[1::2]))

    monthly_data = dict()
    for pos in month_label_positions:
        summary_fields = ''.join(
            str(i) for i in split_text[pos + 1].partition('Total Lots:')[1:3])
        monthly_data[split_text[pos]] = split_summary_fields(
            summary_fields)

    return monthly_data


sample_files = glob.glob('./sample pages/*.html')

with open('sets_2012_info.csv', 'w', newline='') as info_csv, \
     open('sets_2012_prices.csv', 'w', newline='') as prices_csv:

    info_fields = ['Set number', 'Name', 'Set type', 'Theme group', 'Theme',
                   'Subtheme', 'Year released', 'Tags', 'Dimensions', 'Weight',
                   'Pieces', 'Minifigs', 'RRP', 'Age range', 'Packaging',
                   'Availability']
    prices_fields = ['Set number', 'Name', 'Year', 'Month', 'Total Lots',
                     'Total Qty', 'Min Price', 'Avg Price', 'Qty Avg Price',
                     'Max Price']

    info_csv_writer = csv.DictWriter(info_csv, fieldnames=info_fields, delimiter=';')
    info_csv_writer.writeheader()

    prices_csv_writer = csv.DictWriter(prices_csv, fieldnames=prices_fields, delimiter=';')
    prices_csv_writer.writeheader()

    sets_2012 = get_sets_from_year('sets_2012.csv')
    sets_not_found = []

    for (lego_id, variant) in sets_2012:
        print('Lego: {}-{}'.format(lego_id, variant))
        brickset_page = lh.parse(urllib.request.urlopen(
            'https://brickset.com/sets/' + '{}-{}'.format(lego_id, variant)))
        bricklink_page = lh.parse(urllib.request.urlopen(
            'https://www.bricklink.com/v2/catalog/catalogitem_pgtab.page?S='
            + '{}-{}'.format(lego_id, variant)
            + '&st=2&gm=1&gc=0&ei=0&prec=1&showflag=0&showbulk=0&currency=1'))

        try:
            infobox_els = brickset_page.xpath('//dl[dt="Set number"]')[0]
            pg_els = bricklink_page.xpath('//table[@class="pcipgInnerTable"]')[0]
        except IndexError:
            sets_not_found.append('{}-{}'.format(lego_id, variant))
            pass
        else:
            infobox = parse_infobox(infobox_els)
            price_guide = parse_price_guide(pg_els.text_content())

            info_csv_writer.writerow({**{'Set number': lego_id}, **infobox})

            for date, price_summary in price_guide.items():
                month, year = date.split(' ')
                data = {**{'Set number': lego_id, 'Month': month, 'Year': year},
                        **{'Name': infobox['Name']},
                        **price_summary}
                prices_csv_writer.writerow(data)

    print('{} LEGOs not found: {}'.format(len(sets_not_found), ', '.join(sets_not_found)))
