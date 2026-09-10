# AI video evaluation protocol

The project currently has a working pipeline and local job server, but no
measured end-to-end quality benchmark is claimed. Before publishing benchmark
numbers, create a small, non-sensitive set of representative English topics.

For each topic, record:

- whether the generated script follows the requested topic and stays within the
  requested duration;
- whether narration is present and the audio/video durations are aligned;
- whether selected visuals cover the planned scenes and are licensed for use;
- whether captions are readable and timed to the narration;
- whether the output is created successfully, including provider failures and
  empty-result cases.

Keep the topic set, provider/model versions, random or sampling settings, and
failure cases with any reported results. Do not describe the project as
end-to-end validated until this smoke/evaluation run has been completed.
