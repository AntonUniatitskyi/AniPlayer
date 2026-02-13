import asyncio
import logging
import re
import sys
import time
from difflib import SequenceMatcher

import aiohttp
from asgiref.sync import sync_to_async
from django.db import transaction
from django.utils import timezone

from .models import (AnimeTitle, Episode, Franchise, Genre, Subscription,
                     UserAnimeList, WatchLog)


stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter('%(message)s'))
if sys.platform == "win32":
    import codecs
    stream_handler.stream = codecs.getwriter("utf-8")(sys.stdout.buffer)

# Konfig
BASE_SITE_URL = "https://aniliberty.top"
SHIKIMORI_API = "https://shikimori.one/api/animes"
CONCURENT_REQUESTS = 20

logger = logging.getLogger('django')

stream_handler = logging.StreamHandler()
logger.addHandler(stream_handler)


def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def clean_shikimori_description(text):
    if not text:
        return ""
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'<.*?>', '', text)
    return text.strip()


async def fetch_json(session, url, params=None, retries=3):
    for i in range(retries):
        try:
            async with session.get(url, params=params, timeout=15) as response:
                if response.status == 200:

                    return await response.json()
                elif response.status == 429:
                    wait_time = (i + 1) * 7
                    logger.warning(
                        f" [!] Лимит запросов. Ждем {wait_time} сек. (Попытка {i+1}/{retries})")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f" [!] Ошибка API {response.status} на {url}")

                    return None
        except Exception as e:
            logger.error(f" [!] Ошибка сети: {e}")
            await asyncio.sleep(2)

    return None


async def fetch_detail_data(sem, session, ani_id):
    url = f"{BASE_SITE_URL}/api/v1/anime/releases/{ani_id}"
    franchise_url = f"{BASE_SITE_URL}/api/v1/anime/franchises/release/{ani_id}"
    async with sem:
        release_json = await fetch_json(session, url)
        if not release_json:
            return None

        await asyncio.sleep(0.1)
        franchise_data = await fetch_json(session, franchise_url)
        if franchise_data:
            clean_fr_data = franchise_data.get('data') if isinstance(
                franchise_data, dict) and 'data' in franchise_data else franchise_data
            release_json['fetched_franchise'] = clean_fr_data

        return release_json


# Load Anilibria
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
            final_shiki_id = rel_data.get('shikimori_id')

            name_ru = rel_data.get('name', {}).get('main')
            name_en = rel_data.get('name', {}).get('english')
            year_val = rel_data.get('year')
            if year_val:
                try:
                    year_val = int(year_val)
                except (ValueError, TypeError):
                    year_val = None

            type_obj = rel_data.get('type')
            kind_val = None
            kind_desc = None
            if isinstance(type_obj, dict):
                kind_val = type_obj.get('value')       # "TV", "MOVIE", etc.
                kind_desc = type_obj.get('description')

            poster_obj = rel_data.get('poster', {})
            poster_path = None
            if final_shiki_id:
                poster_path = f"https://shikimori.one/system/animes/original/{final_shiki_id}.jpg"
            if not poster_path:
                poster_obj = rel_data.get('poster', {})
                if poster_obj.get('optimized'):
                    poster_path = poster_obj['optimized'].get(
                        'preview') or poster_obj['optimized'].get('thumbnail')

                if not poster_path:
                    poster_path = poster_obj.get(
                        'preview') or poster_obj.get('thumbnail')
                if poster_path and poster_path.startswith('/'):
                    poster_path = BASE_SITE_URL + poster_path
                api_updated = rel_data.get('updated_at')
                if not api_updated:
                    api_updated = timezone.now()
                anime_obj = AnimeTitle.objects.filter(
                    anilibria_id=ani_id).first()

                update_defaults = {
                    'source': 'anilibria',
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
                }
                if final_shiki_id:
                    update_defaults['shikimori_id'] = final_shiki_id

                anime_obj, created = AnimeTitle.objects.update_or_create(
                    anilibria_id=ani_id,
                    defaults=update_defaults
                )

                if created:
                    stats['anime_created'] += 1
                else:
                    stats['anime_updated'] += 1

                fetched_fr_data = rel_json.get('fetched_franchise')
                if fetched_fr_data:
                    fr_list = fetched_fr_data if isinstance(
                        fetched_fr_data, list) else [fetched_fr_data]

                    for fr_item in fr_list:
                        fr_name = fr_item.get('name')
                        fr_id = fr_item.get('id')

                        if fr_name:
                            franchise_obj, _ = Franchise.objects.get_or_create(
                                name=fr_name)
                            anime_obj.franchise = franchise_obj
                            releases_in_fr = fr_item.get(
                                'franchise_releases', [])
                            found_order = False
                            for rel in releases_in_fr:
                                r_id = rel.get('release_id')
                                if str(r_id) == str(ani_id):
                                    sort_order = rel.get('sort_order')
                                    if sort_order is not None:
                                        anime_obj.franchise_order = int(
                                            sort_order)
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
                            g_name_clean = str(g_name).strip()[:250]
                            if g_name_clean:
                                genre, _ = Genre.objects.get_or_create(
                                    name=g_name_clean)
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
        logger.info(f" Страница {page}: LOAD: Старт загрузки...")
        catalog_data = await fetch_json(session, catalog_url, params=params)
    if not catalog_data:
        logger.error(f"WAR: Страница {page}: Пустой ответ или ошибка сети")
        return False
    items = catalog_data.get('data', [])
    if not items:
        logger.warning(f"WAR: Страница {page}: Нет элементов")
        return False
    detail_tasks = [fetch_detail_data(
        sem, session, item.get('id')) for item in items]
    detail_results = await asyncio.gather(*detail_tasks)
    await sync_to_async(save_batch_to_db)(detail_results, stats)
    logger.info(f"> Страница {page} готова.")

    return True


async def runner(full_load):
    conn = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300)
    stats = {'anime_created': 0, 'anime_updated': 0, 'episodes_saved': 0}
    catalog_url = f"{BASE_SITE_URL}/api/v1/anime/catalog/releases"
    sem = asyncio.Semaphore(CONCURENT_REQUESTS)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
    }
    logger.info(f"!! Запуск парсера...")

    async with aiohttp.ClientSession(headers=headers, connector=conn) as session:
        max_pages = 5000 if full_load else 5
        batch_size = 10

        for i in range(1, max_pages + 1, batch_size):
            chunk_tasks = []
            current_batch_range = range(i, min(i + batch_size, max_pages + 1))
            logger.info(
                f"\n--- Формирование пачки страниц {list(current_batch_range)} ---")

            for page in current_batch_range:
                task = asyncio.create_task(process_page(
                    page, session, sem, catalog_url, stats))
                chunk_tasks.append(task)

            if chunk_tasks:
                results = await asyncio.gather(*chunk_tasks)
                if not any(results):
                    logger.warning(
                        f"\nSTOP: Все страницы в пачке пустые. Похоже, каталог закончился на странице {i-1}.")
                    break

    return stats


def merge_and_delete_titles(main_anime, duplicate_anime):
    with transaction.atomic():
        user_lists = UserAnimeList.objects.filter(anime=duplicate_anime)

        for entry in user_lists:
            if not UserAnimeList.objects.filter(user=entry.user, anime=main_anime).exists():
                entry.anime = main_anime
                entry.save()
            else:
                entry.delete()

        WatchLog.objects.filter(anime=duplicate_anime).update(anime=main_anime)
        subs = Subscription.objects.filter(anime=duplicate_anime)

        for s in subs:
            if not Subscription.objects.filter(user=s.user, anime=main_anime).exists():
                s.anime = main_anime
                s.save()
            else:
                s.delete()

        duplicate_name = duplicate_anime.name_ru
        duplicate_anime.delete()
        logger.info(
            f"   [MERGE] Поглощен дубликат: {duplicate_name} -> {main_anime.name_ru}")


async def get_shikimori_franchise(session, shiki_id):
    url = f"https://shikimori.one/api/animes/{shiki_id}/franchise"
    data = await fetch_json(session, url)

    if not data or 'nodes' not in data:
        return None, 0

    nodes = data.get('nodes', [])
    if not nodes:
        return None, 0

    root_node = nodes[0]
    current_weight = 0
    for node in nodes:
        if str(node.get('id')) == str(shiki_id):
            current_weight = node.get('weight', 0)
            break

    return root_node.get('name'), current_weight


def save_shikimori_detailed(data, stats=None, franchise_name=None, franchise_order=0):
    with transaction.atomic():
        shiki_id = data.get('id')

        if not shiki_id:
            return None

        anime_obj = AnimeTitle.objects.filter(shikimori_id=shiki_id).first()
        raw_desc = data.get('description') or data.get(
            'description_html') or ""
        clean_desc = clean_shikimori_description(raw_desc)
        poster = ""

        if data.get('image'):
            poster = f"https://shikimori.one{data['image'].get('original')}"

        defaults = {
            'name_ru': data.get('russian') or data.get('name'),
            'name_en': data.get('name'),
            'description': clean_desc,
            'poster_path': poster,
            'year': data.get('aired_on', '')[:4] if data.get('aired_on') else None,
            'kind': data.get('kind', 'tv').upper(),
            'kind_ru': data.get('kind'),
            'updated_at': timezone.now(),
        }

        if anime_obj:
            for key, value in defaults.items():
                setattr(anime_obj, key, value)
            anime_obj.save()
            if stats:
                stats['kodik_skipped'] += 1
        else:
            defaults.update({
                'shikimori_id': shiki_id,
                'source': 'shikimori',
                'code': f"shiki-{shiki_id}",
            })
            anime_obj = AnimeTitle.objects.create(**defaults)
            if stats:
                stats['kodik_created'] += 1

        if franchise_name:
            fr_obj, _ = Franchise.objects.get_or_create(name=franchise_name)
            anime_obj.franchise = fr_obj
            anime_obj.franchise_order = franchise_order

        genre_objs = []
        for g in data.get('genres', []):
            g_name = g.get('russian') or g.get('name')
            if g_name:
                genre, _ = Genre.objects.get_or_create(
                    name=g_name.strip()[:250])
                genre_objs.append(genre)

        if genre_objs:
            anime_obj.genres.set(genre_objs)

        return anime_obj


async def link_anilibria_to_shikimori():
    targets = await sync_to_async(list)(
        AnimeTitle.objects.filter(
            anilibria_id__isnull=False,
            shikimori_id__isnull=True
        )
    )

    if not targets:
        logger.info("Все доступные тайтлы Анилибрии уже имеют ID.")
        return

    logger.info(f"--- [START] Привязка ID для {len(targets)} тайтлов ---")

    async with aiohttp.ClientSession() as session:
        for anime in targets:
            clean_name = re.sub(r'\[.*?\]', '', anime.name_ru).strip()
            search_url = SHIKIMORI_API
            results = await fetch_json(session, search_url, params={'search': clean_name, 'limit': 5})

            if not results:
                logger.warning(f"   [NOT FOUND] {clean_name}")
                continue

            best_match = None
            max_score = 0

            for res in results:
                if not isinstance(res, dict):
                    continue
                score_ru = similarity(clean_name, res.get('russian', '') or '')
                score_en = similarity(clean_name, res.get('name', '') or '')
                current_score = max(score_ru, score_en)
                kind_shiki = (res.get('kind') or '').lower()
                if 'ova' in clean_name.lower() and kind_shiki != 'ova':
                    current_score -= 0.2
                if 'спешл' in clean_name.lower() and kind_shiki not in ['special', 'ova']:
                    current_score -= 0.2
                if 'фильм' in clean_name.lower() and kind_shiki != 'movie':
                    current_score -= 0.2

                if current_score > max_score:
                    max_score = current_score
                    best_match = res
            if not best_match or max_score < 0.6:
                logger.warning(
                    f"   [LOW SCORE] {clean_name} ({round(max_score, 2)})")
                continue

            shiki_id = best_match['id']
            collision = await sync_to_async(AnimeTitle.objects.filter(shikimori_id=shiki_id).first)()

            if collision and collision.pk != anime.pk:
                if collision.anilibria_id is not None:
                    # Если ID реально занят другим качественным тайтлом - только тогда SKIP
                    logger.warning(
                        f"   [SKIP] Конфликт ID {shiki_id}: '{clean_name}' vs '{collision.name_ru}'")
                    continue
                else:
                    await sync_to_async(merge_and_delete_titles)(anime, collision)

            anime.shikimori_id = shiki_id
            img_data = best_match.get('image')
            if isinstance(img_data, dict):
                original_path = img_data.get('original')
                if original_path:
                    anime.poster_path = f"https://shikimori.one{original_path}"

            await sync_to_async(anime.save)()
            logger.info(
                f"   [OK] {anime.name_ru} -> ID {shiki_id} (Score: {round(max_score, 2)})")

            await asyncio.sleep(0.6)

    logger.info("--- [BATCH DONE] Пачка обработана ---")


async def fetch_shikimori_catalog(limit_pages, stats=None):
    base_url = SHIKIMORI_API
    statuses = ['released', 'ongoing']

    async with aiohttp.ClientSession() as session:
        for status in statuses:
            logger.info(f"--- Начинаю сбор тайтлов со статусом: {status} ---")
            for page in range(1, limit_pages + 1):
                logger.info(f"Shikimori: Сканирование страницы {page}...")

                list_data = await fetch_json(session, base_url, params={
                    'kind': 'tv,movie,ova,ona',
                    'status': status,
                    'limit': 50,
                    'order': 'popularity',
                    'page': page
                })

                if not list_data:
                    break

                for item in list_data:
                    shiki_id = item['id']

                    anime_in_db = await sync_to_async(
                        AnimeTitle.objects.filter(shikimori_id=shiki_id).first
                    )()

                    if not anime_in_db or not anime_in_db.description:
                        detail_url = f"{base_url}/{shiki_id}"
                        detail_data = await fetch_json(session, detail_url)

                        if detail_data:
                            fr_name, fr_order = await get_shikimori_franchise(session, shiki_id)
                            await sync_to_async(save_shikimori_detailed)(detail_data, stats, franchise_name=fr_name,
                            franchise_order=fr_order)
                            await asyncio.sleep(0.7)

                logger.info(f"Страница {page} полностью обработана.")


def fetch_full_sync(full_load=False):
    start_time = time.time()

    async def main_task():
        logger.info("\n=== ШАГ 1: ANILIBRIA ===")
        stats = await runner(full_load)

        stats.setdefault('kodik_created', 0)
        stats.setdefault('kodik_skipped', 0)
        logger.info("\n=== ШАГ 2: ПРИВЯЗКА ID К АНИЛИБРИИ ===")
        await link_anilibria_to_shikimori()

        logger.info("--- STEP 3: FILLING CATALOG VIA SHIKIMORI ---")
        pages = 30 if full_load else 5
        await fetch_shikimori_catalog(limit_pages=pages, stats=stats)

        return stats

    final_stats = asyncio.run(main_task())
    duration = round(time.time() - start_time, 1)
    total_new = final_stats.get('anime_created', 0) + \
        final_stats.get('kodik_created', 0)
    total_updated = final_stats.get(
        'anime_updated', 0) + final_stats.get('kodik_skipped', 0)

    logger.info(f"""
== --- ПОЛНЫЙ ОТЧЕТ СИНХРОНИЗАЦИИ ({duration}s) ---
- Новых тайтлов добавлено: {total_new}
- Существующих обновлено: {total_updated}
- Эпизодов сохранено: {final_stats.get('episodes_saved', 0)}
------------------------------------------------------
    """)

    return total_new, total_updated
