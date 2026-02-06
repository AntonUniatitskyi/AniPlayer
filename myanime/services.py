import asyncio
import time
from django.utils import timezone
import aiohttp
import logging
import requests
from asgiref.sync import sync_to_async
from django.db import transaction
from django.conf import settings
from anime_parsers_ru import KodikParser

from .models import AnimeTitle, Episode, Genre, Franchise

CONCURENT_REQUESTS = 20
BASE_SITE_URL = "https://aniliberty.top"

kodik_parser = KodikParser(validate_token=False)
logger = logging.getLogger('django')

# Оставляем вывод в консоль для удобства
stream_handler = logging.StreamHandler()
logger.addHandler(stream_handler)

async def fetch_json(session, url, params=None):
    try:
        async with session.get(url, params=params, timeout=10) as response:
            if response.status != 200:
                return None
            return await response.json()
    except Exception as e:
        logger.error(f"   ⚠️ Ошибка запроса {url}: {e}")
        return None


async def fetch_detail_data(sem, session, ani_id):
    url = f"{BASE_SITE_URL}/api/v1/anime/releases/{ani_id}"
    franchise_url = f"{BASE_SITE_URL}/api/v1/anime/franchises/release/{ani_id}"
    async with sem:
        release_data = await fetch_json(session, url)
        if not release_data:
            return None
        await asyncio.sleep(0.05)
        franchise_data = await fetch_json(session, franchise_url)
        if franchise_data:
            # Если это словарь с ключом data (стандарт JSON API), достаем его, иначе берем как есть
            clean_fr_data = franchise_data.get('data') if isinstance(franchise_data, dict) and 'data' in franchise_data else franchise_data
            release_data['fetched_franchise'] = clean_fr_data
        return release_data


def save_batch_to_db(batch_data, stats):
    with transaction.atomic():
        for rel_json in batch_data:
            if not rel_json:
                continue

            rel_data = rel_json.get('data') if 'data' in rel_json and isinstance(
                rel_json['data'], dict) else rel_json
            if not rel_data:
                continue

            ani_id = rel_data.get('id')
            if not ani_id:
                continue

            name_ru = rel_data.get('name', {}).get('main')
            name_en = rel_data.get('name', {}).get('english')


            poster_obj = rel_data.get('poster', {})
            poster_path = None
            if poster_obj.get('optimized'):
                poster_path = poster_obj['optimized'].get(
                    'preview') or poster_obj['optimized'].get('thumbnail')
                if not poster_path:
                    poster_path = poster_obj.get(
                        'preview') or poster_obj.get('thumbnail')
                if poster_path and poster_path.startswith('/'):
                    poster_path = BASE_SITE_URL + poster_path

                year_val = rel_data.get('year')
                if year_val:
                    try:
                        year_val = int(year_val)
                    except (ValueError, TypeError):
                        year_val = None

                api_updated = rel_data.get('updated_at')
                if not api_updated:
                    api_updated = timezone.now()

                anime_obj = AnimeTitle.objects.filter(anilibria_id=ani_id).first()
                current_shiki_id = anime_obj.shikimori_id if anime_obj else None
                json_shiki_id = rel_data.get('shikimori_id')
                final_shiki_id = json_shiki_id if json_shiki_id else current_shiki_id

                if not final_shiki_id and name_ru:
                    print(f"🕵️ Ищу ID для: {name_ru} ...")
                    try:
                        res = kodik_parser.search(title=name_ru, limit=1)
                        if not res and name_en:
                            res = kodik_parser.search(title=name_en, limit=1)
                        if res:
                            found_id = res[0].get('shikimori_id')
                            if found_id:
                                final_shiki_id = int(found_id)
                                print(f"   ✅ Нашел! ID: {final_shiki_id}")
                        else:
                            print(f"   ⚠️ Ничего не найдено в Kodik.")
                        time.sleep(0.3)
                    except Exception as e:
                        print(f"   ❌ Ошибка поиска: {e}")

                type_obj = rel_data.get('type')
                kind_val = None
                kind_desc = None
                if isinstance(type_obj, dict):
                    kind_val = type_obj.get('value')       # "TV", "MOVIE", etc.
                    kind_desc = type_obj.get('description')
                anime_obj, created = AnimeTitle.objects.update_or_create(
                    anilibria_id=ani_id,
                    defaults={
                        'code': rel_data.get('alias'),
                        'name_ru': name_ru,
                        'name_en': name_en,
                        'description': rel_data.get('description', '') or '',
                        'poster_path': poster_path or '',
                        'player_url': '',
                        'updated_at': api_updated,
                        'kind': kind_val,
                        'kind_ru': kind_desc,
                        'year': year_val,
                        'shikimori_id': final_shiki_id,
                    }
                )
                if created:
                    stats['anime_created'] += 1
                else:
                    stats['anime_updated'] += 1

                fetched_fr_data = rel_json.get('fetched_franchise') # Берем из корня JSON, так как мы туда положили

                # API может вернуть список франшиз или одну. Приводим к списку.
                if fetched_fr_data:
                    fr_list = fetched_fr_data if isinstance(fetched_fr_data, list) else [fetched_fr_data]

                    for fr_item in fr_list:
                        # fr_item - это объект франшизы
                        fr_name = fr_item.get('name')
                        fr_id = fr_item.get('id')

                        if fr_name:
                            franchise_obj, _ = Franchise.objects.get_or_create(name=fr_name)
                            anime_obj.franchise = franchise_obj
                            releases_in_fr = fr_item.get('franchise_releases', [])
                            found_order = False
                            for rel in releases_in_fr:
                                r_id = rel.get('release_id')

                                if str(r_id) == str(ani_id):
                                    sort_order = rel.get('sort_order')

                                    if sort_order is not None:
                                        anime_obj.franchise_order = int(sort_order)
                                        found_order = True
                                    break
                            if not found_order:
                                anime_obj.franchise_order = 0

                            anime_obj.save()
                            break

                genres_list = rel_data.get('genres', [])
                if genres_list:
                    genre_objects = []
                    for genre_item in genres_list:
                        if isinstance(genre_item, dict):
                            g_name = genre_item.get('name')
                        else:
                            g_name = str(genre_item)

                        if g_name:
                            # Чистим и обрезаем
                            g_name_clean = str(g_name).strip()[:250]

                            if g_name_clean:
                                genre, _ = Genre.objects.get_or_create(name=g_name_clean)
                                genre_objects.append(genre)

                    anime_obj.genres.set(genre_objects)


                episodes_list = rel_data.get('episodes', [])
                if episodes_list:
                    def fix_url(u):
                        if not u:
                            return None
                        if u.startswith('/'):
                            return BASE_SITE_URL + u
                        if u.startswith('//'):
                            return 'https:' + u
                        return u
                    for ep in episodes_list:
                        opening_data = ep.get('opening') or {}
                        ending_data = ep.get('ending') or {}

                        Episode.objects.update_or_create(
                            anime=anime_obj,
                            ordinal=ep['ordinal'],
                            defaults={
                                'hls_480': fix_url(ep.get('hls_480')),
                                'hls_720': fix_url(ep.get('hls_720')),
                                'hls_1080': fix_url(ep.get('hls_1080')),

                                'skip_op_start': opening_data.get('start'),
                                'skip_op_end': opening_data.get('stop'),

                                'skip_ed_start': ending_data.get('start'),
                                'skip_ed_end': ending_data.get('stop'),
                            }
                        )
                        stats['episodes_saved'] += 1


async def process_page(page, session, sem, catalog_url, stats):
    params = {'limit': 12, 'page': page, 'f[sorting]': 'FRESH_AT_DESC'}

    async with sem:
        logger.info(f" Страница {page}: ⏳ Старт загрузки...")
        catalog_data = await fetch_json(session, catalog_url, params=params)

    if not catalog_data:
        logger.error(f"⚠️ Страница {page}: Пустой ответ или ошибка сети")
        return False

    items = catalog_data.get('data', [])
    if not items:
        logger.warning(f"⚠️ Страница {page}: Нет элементов")
        return False

    detail_tasks = [fetch_detail_data(
        sem, session, item.get('id')) for item in items]
    detail_results = await asyncio.gather(*detail_tasks)

    # Сохраняем в БД
    await sync_to_async(save_batch_to_db)(detail_results, stats)
    logger.info(f"✅ Страница {page} готова.")
    return True


async def runner(full_load):
    conn = aiohttp.TCPConnector(limit=None, ttl_dns_cache=300)

    stats = {'anime_created': 0, 'anime_updated': 0, 'episodes_saved': 0}
    catalog_url = f"{BASE_SITE_URL}/api/v1/anime/catalog/releases"

    sem = asyncio.Semaphore(CONCURENT_REQUESTS)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
    }

    logger.info(f"🚀 Запуск парсера...")

    async with aiohttp.ClientSession(headers=headers, connector=conn) as session:
        max_pages = 5000 if full_load else 5
        batch_size = 10

        for i in range(1, max_pages + 1, batch_size):
            chunk_tasks = []

            current_batch_range = range(i, min(i + batch_size, max_pages + 1))

            logger.info(
                f"\n--- 📦 Формирование пачки страниц {list(current_batch_range)} ---")

            for page in current_batch_range:
                task = asyncio.create_task(process_page(
                    page, session, sem, catalog_url, stats))
                chunk_tasks.append(task)

            if chunk_tasks:
                results = await asyncio.gather(*chunk_tasks)
                if not any(results):
                    logger.warning(
                        f"\n🛑 Все страницы в пачке пустые. Похоже, каталог закончился на странице {i-1}.")
                    break

    return stats


def fetch_anilibria_updates(full_load=False):
    stats = asyncio.run(runner(full_load))
    logger.info(
        f"\n🏁 ИТОГ: Создано {stats['anime_created']} аниме, обновлено {stats['anime_updated']} аниме, сохранено {stats['episodes_saved']} эпизодов.")
    return stats['anime_created'], stats['anime_updated']
