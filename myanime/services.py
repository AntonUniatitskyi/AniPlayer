import requests
import time
from django.db import transaction
from .models import AnimeTitle, Episode

def fetch_anilibria_updates(full_load=False):

    base_site_url = "https://aniliberty.top"

    catalog_url = f"{base_site_url}/api/v1/anime/catalog/releases"
    release_url_tmpl = f"{base_site_url}/api/v1/anime/releases/{{}}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
    }

    page = 1
    max_pages = 5000 if full_load else 5
    stats = {'anime_created': 0, 'anime_updated': 0, 'episodes_saved': 0}

    print(f"🚀 Запуск парсера (Anime + Episodes)...")

    with requests.Session() as session:
        session.headers.update(headers)

        while page <= max_pages:
            try:
                print(f"📡 Страница {page}: Загрузка каталога...")
                params = {'limit': 12, 'page': page, 'f[sorting]': 'FRESH_AT_DESC'}

                resp = session.get(catalog_url, params=params, timeout=10)
                resp.raise_for_status()
                items = resp.json().get('data', [])

                if not items:
                    print(f"⚠️ Страница {page} пуста.")
                    break

                for item in items:
                    ani_id = item.get('id')

                    try:
                        time.sleep(0.2)
                        rel_resp = session.get(release_url_tmpl.format(ani_id), timeout=5)
                        if rel_resp.status_code != 200: continue

                        rel_json = rel_resp.json()
                        rel_data = rel_json.get('data') if 'data' in rel_json and isinstance(rel_json['data'], dict) else rel_json

                        poster_obj = rel_data.get('poster', {})
                        poster_path = None
                        if poster_obj.get('optimized'):
                            poster_path = poster_obj['optimized'].get('preview') or poster_obj['optimized'].get('thumbnail')
                        if not poster_path:
                            poster_path = poster_obj.get('preview') or poster_obj.get('thumbnail')

                        if poster_path and poster_path.startswith('/'):
                            poster_path = base_site_url + poster_path

                        with transaction.atomic():
                            anime_obj, created = AnimeTitle.objects.update_or_create(
                                anilibria_id=ani_id,
                                defaults={
                                    'code': rel_data.get('alias'),
                                    'name_ru': rel_data.get('name', {}).get('main'),
                                    'name_en': rel_data.get('name', {}).get('english'),
                                    'description': rel_data.get('description', '') or '',
                                    'poster_path': poster_path or '',
                                    'player_url': ''
                                }
                            )

                            if created: stats['anime_created'] += 1
                            else: stats['anime_updated'] += 1

                            episodes_list = rel_data.get('episodes', [])

                            if episodes_list:

                                def fix_url(u):
                                    if not u: return None
                                    if u.startswith('/'): return base_site_url + u
                                    if u.startswith('//'): return 'https:' + u
                                    return u
                                for ep in episodes_list:
                                    player_link = None

                                    opening_data = ep.get('opening')
                                    ending_data = ep.get('ending')

                                    op_start = op_end = None
                                    ed_start = ed_end = None

                                    if opening_data and isinstance(opening_data, dict):
                                        op_start = opening_data.get('start')
                                        op_end = opening_data.get('stop')

                                    if ending_data and isinstance(ending_data, dict):
                                        ed_start = ending_data.get('start')
                                        ed_end = ending_data.get('stop')
                                    Episode.objects.update_or_create(
                                        anime=anime_obj,
                                        ordinal=ep['ordinal'],
                                        defaults={
                                            'hls_480': fix_url(ep.get('hls_480')),
                                            'hls_720': fix_url(ep.get('hls_720')),
                                            'hls_1080': fix_url(ep.get('hls_1080')),

                                            'skip_op_start': op_start,
                                            'skip_op_end': op_end,
                                            'skip_ed_start': ed_start,
                                            'skip_ed_end': ed_end,
                                        }
                                    )
                                    stats['episodes_saved'] += 1

                    except Exception as e:
                        print(f"   Err ID {ani_id}: {e}")
                        continue

                print(f"✅ Страница {page} готова.")
                page += 1

            except Exception as e:
                print(f"❌ Критическая ошибка: {e}")
                break

    print(f"\n🏁 ИТОГ: Создано {stats['anime_created']}, Обновлено {stats['anime_updated']}, Серий {stats['episodes_saved']}")
    return stats['anime_created'], stats['anime_updated']
