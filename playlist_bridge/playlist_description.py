"""A replaceable summary derived from the original source description."""
MARKER='\n\n— Playlist Bridge —\n'

def render(description,playlist,source_count,matched_count,missing_count,ignored_count=0):
    original=(description or '').split(MARKER,1)[0].rstrip()
    detail=(f"Source: {playlist.get('source_url','')}\n"
            f"Last successful sync: {playlist['last_synced']}\n"
            f"Tracks: {source_count} source · {matched_count} matched · {missing_count} missing · {ignored_count} ignored")
    return original+MARKER+detail
