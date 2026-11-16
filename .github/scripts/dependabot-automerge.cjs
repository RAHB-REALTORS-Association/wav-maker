const { execFileSync } = require('node:child_process');
const { readFileSync } = require('node:fs');

// Pass API values as arguments, never interpolate PR content into shell commands.
function api(method, endpoint, fields = {}) {
    const args = ['api', '--method', method, endpoint];
    for (const [key, value] of Object.entries(fields)) args.push('-f', `${key}=${value}`);
    const output = execFileSync('gh', args, { encoding: 'utf8' });
    return output.trim() ? JSON.parse(output) : null;
}

async function pages(apiCall, endpoint, key) {
    const items = [];
    for (let page = 1; ; page++) {
        const result = await apiCall('GET', `${endpoint}${endpoint.includes('?') ? '&' : '?'}per_page=100&page=${page}`);
        const batch = key ? result[key] : result;
        items.push(...batch);
        if (batch.length < 100) return items;
    }
}

function eligible(pr, repository, branch, sha) {
    // Only these bot-generated groups are eligible. dependabot.yml restricts
    // each group to minor/patch updates; majors remain separate manual PRs.
    const allowedGroup = /^dependabot\/(pip|github_actions|docker)\/patch-and-minor(?:-security)?-[a-z0-9]+$/;
    return pr.state === 'open' && !pr.draft && pr.user.login === 'dependabot[bot]' &&
        pr.head.repo?.full_name === repository && pr.base.repo.full_name === repository &&
        pr.base.ref === branch && allowedGroup.test(pr.head.ref) && pr.head.sha === sha;
}

function checksReady(checks, statuses) {
    const required = ['Run Tests', 'Build and Publish Docker Image'];
    // Required checks must actually pass, not merely be skipped or neutral.
    if (!required.every(name => checks.some(check => check.name === name &&
        check.app?.slug === 'github-actions' && check.status === 'completed' && check.conclusion === 'success'))) return false;
    return checks.every(check => check.status === 'completed' &&
        ['success', 'skipped', 'neutral'].includes(check.conclusion)) &&
        statuses.every(status => status.state === 'success');
}

async function autoMerge(event, apiCall = api, wait = ms => new Promise(resolve => setTimeout(resolve, ms))) {
    const run = event.workflow_run;
    const repository = event.repository.full_name;
    const branch = event.repository.default_branch;
    if (run.event !== 'pull_request' || run.conclusion !== 'success' ||
        run.head_repository?.full_name !== repository) return;
    const root = `repos/${repository}`;
    const owner = repository.split('/')[0];
    const prs = await pages(apiCall, `${root}/pulls?state=open&head=${encodeURIComponent(`${owner}:${run.head_branch}`)}`);
    for (const candidate of prs) {
        for (let attempt = 0; attempt < 20; attempt++) {
            // Re-read on every attempt to reject new commits and closed/draft PRs.
            const pr = await apiCall('GET', `${root}/pulls/${candidate.number}`);
            if (!eligible(pr, repository, branch, run.head_sha)) break;
            const checks = await pages(apiCall, `${root}/commits/${run.head_sha}/check-runs?filter=latest`, 'check_runs');
            const statuses = await pages(apiCall, `${root}/commits/${run.head_sha}/statuses`);
            // Commit statuses can have history; only the most recent per context counts.
            const latest = [...new Map(statuses.slice().reverse().map(status => [status.context, status])).values()];
            if (checksReady(checks, latest)) {
                const merged = await apiCall('PUT', `${root}/pulls/${pr.number}/merge`, {
                    sha: run.head_sha, merge_method: 'merge',
                });
                if (!merged.merged) throw new Error(`GitHub did not merge PR #${pr.number}`);
                console.log(`Merged Dependabot PR #${pr.number} at ${run.head_sha}`);
                // GITHUB_TOKEN merges do not trigger push workflows. Dispatch explicitly
                // so main/latest images still get rebuilt without a stored personal token.
                await apiCall('POST', `${root}/actions/workflows/build-and-publish.yml/dispatches`, { ref: branch });
                return;
            }
            if (checks.some(check => check.status === 'completed' &&
                !['success', 'skipped', 'neutral'].includes(check.conclusion)) ||
                latest.some(status => ['error', 'failure'].includes(status.state))) {
                console.log(`Leaving PR #${pr.number} open because a check failed.`);
                break;
            }
            if (attempt === 19) throw new Error(`Timed out waiting for all checks on PR #${pr.number}`);
            await wait(15000);
        }
    }
}

if (require.main === module) {
    autoMerge(JSON.parse(readFileSync(process.env.GITHUB_EVENT_PATH, 'utf8')))
        .catch(error => { console.error(error); process.exitCode = 1; });
}
module.exports = { autoMerge, eligible, checksReady };
