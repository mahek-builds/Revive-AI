def decide(root_cause,attempts):
    ladder=PLAYBOOKS[root_cause]
    index=min(attempts,len(ladder)-1)
    playbook=ladder[index]
    channel=CHANNEL_MAP(playbook)

    return {
        "playbbok":index,
        "channel":channel
    }