const { test } = require('node:test');
const assert = require('node:assert/strict');
const { autoMerge, eligible, checksReady } = require('../../.github/scripts/dependabot-automerge.cjs');
const repository = 'example/app';
const sha = 'verified-commit';
function pr() {
    return { number: 7, state: 'open', draft: false, user: { login: 'dependabot[bot]' },
        head: { ref: 'dependabot/pip/updates', sha, repo: { full_name: repository } },
        base: { ref: 'main', repo: { full_name: repository } } };
}
function event() {
    return { repository: { full_name: repository, default_branch: 'main' },
        workflow_run: { event: 'pull_request', conclusion: 'success', head_sha: sha,
            head_branch: pr().head.ref, head_repository: { full_name: repository } } };
}
function checks() {
    return ['Run Tests', 'Build and Publish Docker Image'].map(name => ({ name,
        status: 'completed', conclusion: 'success', app: { slug: 'github-actions' } }));
}
function mockApi({ pull = pr(), results = checks(), statuses = [], merge = true } = {}) {
    const calls = [];
    return { calls, api: async (method, path, fields) => {
        calls.push({ method, path, fields });
        if (method === 'PUT') return { merged: merge };
        if (method === 'POST') return null;
        if (path.includes('/check-runs')) return { check_runs: typeof results === 'function' ? results() : results };
        if (path.includes('/statuses')) return statuses;
        if (path.includes('/pulls?')) return [pull];
        return pull;
    } };
}
test('only current, open, same-repository Dependabot PRs targeting main are eligible', () => {
    assert.equal(eligible(pr(), repository, 'main', sha), true);
    const variants = [
        { user: { login: 'person' } }, { draft: true }, { state: 'closed' },
        { head: { ...pr().head, sha: 'new-commit' } },
        { head: { ...pr().head, repo: { full_name: 'fork/app' } } },
        { head: { ...pr().head, ref: 'ordinary-branch' } },
        { base: { ...pr().base, ref: 'release' } },
    ];
    for (const variant of variants) assert.equal(eligible({ ...pr(), ...variant }, repository, 'main', sha), false);
});
test('tests and Docker build must exist and pass as GitHub Actions checks', () => {
    assert.equal(checksReady(checks(), []), true);
    assert.equal(checksReady([], []), false);
    assert.equal(checksReady(checks().slice(0, 1), []), false);
    for (const conclusion of ['skipped', 'neutral', 'failure', 'cancelled', null]) {
        assert.equal(checksReady([{ ...checks()[0], conclusion }, checks()[1]], []), false);
    }
    assert.equal(checksReady([{ ...checks()[0], app: { slug: 'other-app' } }, checks()[1]], []), false);
});
test('other checks and legacy statuses also gate merging', () => {
    for (const status of ['queued', 'in_progress']) {
        assert.equal(checksReady([...checks(), { name: 'extra', status }], []), false);
    }
    assert.equal(checksReady([...checks(), { status: 'completed', conclusion: 'failure' }], []), false);
    for (const state of ['pending', 'failure', 'error']) assert.equal(checksReady(checks(), [{ state }]), false);
    assert.equal(checksReady([...checks(), { status: 'completed', conclusion: 'neutral' }], [{ state: 'success' }]), true);
});
test('merges the verified SHA and dispatches the main build', async () => {
    const mock = mockApi();
    await autoMerge(event(), mock.api);
    assert.deepEqual(mock.calls.filter(call => call.method === 'PUT'), [{ method: 'PUT',
        path: 'repos/example/app/pulls/7/merge', fields: { sha, merge_method: 'merge' } }]);
    assert.deepEqual(mock.calls.at(-1), { method: 'POST',
        path: 'repos/example/app/actions/workflows/build-and-publish.yml/dispatches', fields: { ref: 'main' } });
});
test('ignores fork, failed and non-PR workflow events', async () => {
    for (const change of [{ event: 'push' }, { conclusion: 'failure' }, { head_repository: { full_name: 'fork/app' } }]) {
        const mock = mockApi();
        const input = event();
        Object.assign(input.workflow_run, change);
        await autoMerge(input, mock.api);
        assert.equal(mock.calls.length, 0);
    }
});
test('never writes for a human PR, changed SHA or failing check', async () => {
    for (const options of [{ pull: { ...pr(), user: { login: 'person' } } },
        { pull: { ...pr(), head: { ...pr().head, sha: 'changed' } } },
        { results: [...checks(), { status: 'completed', conclusion: 'failure' }] }]) {
        const mock = mockApi(options);
        await autoMerge(event(), mock.api);
        assert.equal(mock.calls.some(call => call.method !== 'GET'), false);
    }
});
test('waits for pending checks, then rechecks before merging', async () => {
    let attempt = 0;
    let waits = 0;
    const mock = mockApi({ results: () => ++attempt === 1 ? [...checks(), { status: 'queued' }] : checks() });
    await autoMerge(event(), mock.api, async () => { waits++; });
    assert.equal(waits, 1);
    assert.equal(mock.calls.filter(call => call.path === 'repos/example/app/pulls/7').length, 2);
    assert.equal(mock.calls.filter(call => call.method === 'PUT').length, 1);
});
test('old failed commit statuses do not override a newer passing status', async () => {
    const mock = mockApi({ statuses: [{ context: 'external', state: 'success' }, { context: 'external', state: 'failure' }] });
    await autoMerge(event(), mock.api);
    assert.equal(mock.calls.filter(call => call.method === 'PUT').length, 1);
});
test('does not dispatch a build when GitHub refuses the merge', async () => {
    const mock = mockApi({ merge: false });
    await assert.rejects(autoMerge(event(), mock.api), /did not merge/);
    assert.equal(mock.calls.some(call => call.method === 'POST'), false);
});
