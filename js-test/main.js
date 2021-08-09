const SpotifyWebApi = require('spotify-web-api-node');
const base64url = require('base64url');
const Cookies = require("js-cookie");

const viz = require("./viz");
const pako = require('pako');

var clientId = "d85de6c0c70241d1befe36e2c2d382e3";
var redirectUri = "http://localhost:5000/callback";

var spotifyApi = new SpotifyWebApi();

async function auth() {
    function redirectForAuthorizationCode(code_challenge) {
        var data = {
            "client_id": clientId,
            "response_type": "code",
            "redirect_uri": redirectUri,
            "scope": "user-library-read,user-read-recently-played,user-top-read,playlist-read-private",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }
        var query = new URLSearchParams(data).toString();
        var auth_uri = "https://accounts.spotify.com/authorize?" + query;
        // redirect
        window.location.replace(auth_uri);
    }

    async function getAccessToken(authorization_code, code_verifier) {
        var token_uri = `https://accounts.spotify.com/api/token`
        var data = {
            "client_id": clientId,
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": redirectUri,
            "code_verifier": code_verifier,
        };

        var method = "POST";
        var headers = new Headers();
        headers.set("Content-Type", 'application/x-www-form-urlencoded');
        var body = new URLSearchParams(data).toString(); 
        console.log(body);

        var promise = fetch(token_uri, {
            method: method, 
            body: body,
            headers: headers,
        }).then(response => {
            console.log("Request complete! response:", response);
            return response.json().then(
                function(response_body) {
                    var access_token = response_body['access_token'];
                    var refresh_token = response_body['refresh_token'];
                    var expires_in = response_body['expires_in'];
                    expires_in = new Date(new Date().getTime() + (parseInt(expires_in) - 10)  * 1000);
                    console.log("expires in: " + expires_in);
                    Cookies.set("access_token", access_token, {expires: expires_in});
                    Cookies.set("refresh_token", refresh_token);
                    return [access_token, refresh_token];
                }
            );
        });
        return promise;
    }

    async function getRefreshedAccessToken(refresh_token) {
        var token_uri = `https://accounts.spotify.com/api/token`
        var data = {
            "client_id": clientId,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        };

        var method = "POST";
        var headers = new Headers();
        headers.set("Content-Type", 'application/x-www-form-urlencoded');
        var body = new URLSearchParams(data).toString(); 
        console.log(body);

        var promise = fetch(token_uri, {
            method: method, 
            body: body,
            headers: headers,
        }).then(response => {
            console.log("Request complete! response:", response);
            return response.json().then(
                function(response_body) {
                    var access_token = response_body['access_token'];
                    var refresh_token = response_body['refresh_token'];
                    var expires_in = response_body['expires_in'];
                    expires_in = new Date(new Date().getTime() + (parseInt(expires_in) - 10)  * 1000);
                    console.log("expires in: " + expires_in);
                    Cookies.set("access_token", access_token, {expires: expires_in});
                    Cookies.set("refresh_token", refresh_token);
                    return [access_token, refresh_token];
                }
            );
        });
        return promise;
    }


    // https://stackoverflow.com/questions/18118824/javascript-to-generate-random-password-with-specific-number-of-letters
    function cryptoRandomString(length) {
        // https://developer.spotify.com/documentation/general/guides/authorization-guide/#authorization-code-flow-with-proof-key-for-code-exchange-pkce
        // It can contain letters, digits, underscores, periods, hyphens, or tildes.
        var charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-~";
        var i;
        var result = "";
        // https://developer.mozilla.org/en-US/docs/Web/API/Window/crypto
        var crypto = window.crypto || window.msCrypto; // for IE 11
        values = new Uint32Array(length);
        crypto.getRandomValues(values);
        for(i = 0; i < length; i++) {
            result += charset[values[i] % charset.length];
        }
        return result;
    }
    
    async function createChallengeVerifierAndCode() {
        var code_verifier = cryptoRandomString(128);
        var code_verifier_bytes = (new TextEncoder()).encode(code_verifier);
        var hash = await window.crypto.subtle.digest("SHA-256", code_verifier_bytes);
        var code_challenge = base64url(hash);
        return [code_verifier, code_challenge];
    }

    // Check url for auth information
    if (urlParams.get("error")) {
        console.log("User denied access");
    } else if (urlParams.get("code")) {
        var authorization_code = urlParams.get("code");
        console.log("Got auth token: " + authorization_code);
        Cookies.set("authorization_code", authorization_code);
    }

    // Check cookies for auth information
    var code_challenge = Cookies.get("code_challenge");
    var code_verifier = Cookies.get("code_verifier");
    var authorization_code = Cookies.get("authorization_code");
    var access_token = Cookies.get("access_token");
    var refresh_token = Cookies.get("refresh_token");

    if (access_token) {
        return Promise(() => {return [access_token, refresh_token]});
    }

    if (authorization_code && code_verifier) {
        // We've generated an auth_code and code_verifier
        // and been redirected to /callback 
        var access_and_refresh_tokens = getAccessToken(authorization_code, code_verifier);
        Cookies.remove("code_challenge");
        Cookies.remove("code_verifier");
        Cookies.remove("authorization_code");
        return access_and_refresh_tokens;
    } else {
        if (refresh_token) {
            // We have a refresh token on hand and need to get a new access and refresh token
            var access_and_refresh_tokens = getRefreshedAccessToken(refresh_token);
            return access_and_refresh_tokens
        } else {
            // We are starting the auth flow and need to generate a code_verifier and code_challange
            // before redirecting to spotify for an auth_code
            var result = await createChallengeVerifierAndCode();
            code_verifier = result[0];
            code_challenge = result[1];
            Cookies.set("code_verifier", code_verifier);
            Cookies.set("code_challenge", code_challenge);
            redirectForAuthorizationCode(code_challenge);    
        }
    }    
}

function logout() {
    Cookies.remove("code_challenge");
    Cookies.remove("code_verifier");
    Cookies.remove("authorization_code");
    Cookies.remove("access_token");
    Cookies.remove("refresh_token");
    window.location.reload();
}

function initApi() {
    var access_token = Cookies.get("access_token");
    var refresh_token = Cookies.get("refresh_token");
    spotifyApi.setAccessToken(access_token);
    spotifyApi.setRefreshToken(refresh_token);
}

// From: https://github.com/thelinmichael/spotify-web-api-node/issues/217
async function callWithRetry(func, retries=0, max_retries=10) {
    try {
        // console.log("calling func");
        return await func();
    } catch (e) {
        console.log("caught error and trying again");
        if (retries <= max_retries) {
            if (e && e.statusCode === 429) {
                // +1 sec leeway
                const retryAfter = (parseInt(e.headers['retry-after'], 10)) * 1000;
                console.log(`sleeping for: ${retryAfter.toString()}`);
                await new Promise((r) => setTimeout(r, retryAfter));
            }
            return await callWithRetry(func, retries + 1, max_retries);
        } else {
            console.log("hit max retries!")
            throw e;
        }
    }    
}

function callWithOffsetAndLimit(f, offset, limit) {
    return () => {return f({"limit": limit, "offset": offset})};
}

async function enumerateTracks(offset, limit) {
    console.log("getting tracks at " + offset);
    var func = () => {
        return spotifyApi.getMySavedTracks({
            "limit": limit,
            "offset": offset
        })
    }
    return callWithRetry(func, 0, 10).then(
        function(response) {
            console.log("got tracks at: " + offset + " response: " + response);
            var retDict = {};
            for (var [index, track] of response.body.items.entries()) {
                retDict[index + offset] = track;
            }
            return retDict;
        },
        function(error) {
            console.log("error " + error + " at " + offset);
            return {};
        }
    )
}

async function getAllTracks() {
    initApi();

    return spotifyApi.getMySavedTracks().then(
        function (response) {
            console.log("getting all tracks");
            var total = response.body.total;
            var limit = 50;
            var numCalls = parseInt(total / limit) + 1;
            var allData = {};
            var promises = [];
            for (var i = 0; i < numCalls; i++) {
                promises.push(enumerateTracks(i * limit, limit));
            };
            return Promise.all(promises).then(function (allResults) {
                console.log("resolved promises: " + allResults);
                for (var result of allResults) {
                    for (var index in result) {
                        console.log("got data for " + index);
                        allData[index] = result[index];
                    }
                }
                return allData
            }, function(error) {
                console.log("Error resolving promises: " + error);
            });
        }
    )
}

// Unpacks a response from /v1/me/tracks into the desired format
async function unpackTracksResponse(response) {
    var itemsKeysToKeep = ["added_at", "played_at"];
    var trackKeysToKeep = ["artists", "id", "name", "popularity", "uri"];
    var ret = [];
    for (var [idx, item] of response.body.items.entries()) {
        var keep = {};
        for (var key of itemsKeysToKeep) {
            keep[key] = item[key];
        }
        for (var key of trackKeysToKeep) {
            keep[key] = item.track[key];
        }
        ret.push(keep);
    }
    return ret
}

// unpack results from /v1/artists
async function unpackArtistsResponse(response) {
    var artistsKeysToKeep = ["genres", "id",  "name", "popularity", "uri"];
    var ret = [];
    console.log("unpacking " + response.body.artists.length + " artists");
    for (var artist of response.body.artists) {
        var keep = {};
        for (var key of artistsKeysToKeep) {
            keep[key] = artist[key];
        }
        ret.push(keep);
    }
    return ret
}

// unpack results from /v1/audio-features
async function unpackTrackFeaturesResponse(data) {
    var ids = data[0];
    var response = data[1];
    // TODO: thin which features to keep?
    console.log("Features response: ", response, "for ids: ", ids);
    if (response.body.audio_features) {
        return response.body.audio_features;
    } else {
        throw new Error("no audio_features in response" + response.toString());
    }   
}

async function savedTracks() {
    // spotifyApi.getMySavedTracks().then(console.log, console.log);
    var librarySize = (await callWithRetry(() => {return spotifyApi.getMySavedTracks()})).body.total;
    var limit = 50;
    var numCalls = parseInt(librarySize / limit);
    var remainder = (librarySize / limit) - numCalls;
    if (remainder > 0) {
        numCalls += 1;
    }
    // numCalls = 5;
    var promises = [];
    for (var i = 0; i < numCalls; i++) {
        promises.push(
            callWithRetry(
                () => {return spotifyApi.getMySavedTracks({"offset": i * limit, "limit": limit})}
            ).then(unpackTracksResponse, (e) => {throw e})
        );
    }
    var allTracks = await Promise.all(promises).then(
        (result) => {console.log("Got all tracks!"); return result},
        (error) => {console.log("Error while getting all tracks"); throw error}
    );
    var ret = [];
    for (var i = 0; i < numCalls; i++) {
        for (var track of allTracks[i]) {
            ret.push(track);
        }
    }
    return ret;
}

async function featurizeTracks(tracks) {
    var trackIds = [];
    for (var track of tracks) {
        trackIds.push(track.id);
    }
    var promises = [];
    // Get features in chunks of 100 (max number of ids)
    // Make arrays of size 100...
    var limit = 100;
    var numCalls = Math.floor(trackIds.length / limit);
    var remainder = trackIds.length - numCalls * limit;
    if (remainder > 0) {
        numCalls += 1;
    }
    // numCalls = 70;
    console.log("calling", numCalls, "times");
    var promises = [];
    var idSplits = [];
    var call = async function(i, ids) {
        console.log("[inside] call number", i, "ids are", ids);
        return callWithRetry(() => {
            return spotifyApi.getAudioFeaturesForTracks(ids).then(
            function (response) {
                return [ids, response];
            })
        });
    }
    for (var i = 0; i < numCalls; i++) {
        idSplits.push(trackIds.slice(i * limit, (i + 1) * limit));
        promises.push(
            call(
                i * 1, idSplits[i * 1]
            ).then(
                unpackTrackFeaturesResponse, 
                (e) => {console.log("[featurizeTracks] error:", e); throw e}
            )
        );
    }

    var featuresResults = await Promise.all(promises).then(
        (result) => {console.log("Got all features!"); return result;},
        (error) => {console.log("Error while getting all features"); return error;}
    );
    console.log("[featurizeTracks] " + featuresResults.length + " audio-features api calls resolved");
    var features = {};
    for (var featuresResult of featuresResults) {
        console.log("[featurizeTracks] " + featuresResult.length  + " audio-features from call")
        if (featuresResult.length < 100) {
            console.log("[featurizeTracks] featuresResult =", featuresResult);
        } 
        for (var trackFeatures of featuresResult) {
            features[trackFeatures.id] = trackFeatures;
        }
    }
    console.log("[featurizeTracks] Requested features for " + trackIds.length + " tracks and got " + Object.keys(features).length);
    return features
}

async function genresForTracks(tracks) {
    // Use a Set so that we only call the API for each id once
    var artistIds = new Set();
    var totalArtists = 0;
    for (var track of tracks) {
        for (var artist of track.artists) {
            artistIds.add(artist.id);
            totalArtists += 1;
        }
    }
    var numArtists = artistIds.size;
    var promises = [];
    var artistIdBuffer = [];
    // Get artists in chunks of 50 (max number of ids)
    for (var artistId of artistIds) {
        if (artistIdBuffer.length < 49) {
            artistIdBuffer.push(artistId);
        } else {
            artistIdBuffer.push(artistId);
            var bufferClone = artistIdBuffer.slice();
            promises.push(callWithRetry(() => {
                return spotifyApi.getArtists(bufferClone)
            }).then(unpackArtistsResponse, (e) => {throw e}));
            artistIdBuffer = [];
        }
    }
    // Finish remaining artists if number of tracks is not a multiple of 50
    if (artistIdBuffer.length > 0) {
        var bufferClone = artistIdBuffer.slice();
        promises.push(callWithRetry(() => {
            return spotifyApi.getArtists(bufferClone)
        }).then(unpackArtistsResponse, (e) => {throw e}));
        artistIdBuffer = [];
    }
    var artistsResults = await Promise.all(promises).then(
        (result) => {console.log("Got all artists!"); return result},
        (error) => {console.log("Error while getting all artists"); throw error}
    );
    var artistsKeyedById = {};
    var numArtistResults = 0;
    for (var artistResult of artistsResults) {
        numArtistResults += artistResult.length;
    }
    console.log("Total " + totalArtists + ", requested " + numArtists + " artists, and got " + numArtistResults);
    for (var artistResult of artistsResults) {
        console.log(artistResult.length + " artists in result");
        for (var artist of artistResult) {
            artistsKeyedById[artist.id] = artist;
        }
    }
    var genres = [];
    for (var track of tracks) {
        var artists = track.artists;
        var trackGenres = [];
        for (var artist of artists) {
            var artistResult = artistsKeyedById[artist.id];
            if (artistResult) {
                for (var genre of artistResult.genres) {
                    trackGenres.push(genre);
                }
            } else {
                console.log("information for artist " + artist.name + " was not gathered");
                console.log(artistResult);
                console.log(artist.id);
            }
        }
        genres.push(trackGenres);
    }
    return genres
}

async function formatTracksForViz(tracks) {
    var featuresToUse = [
        'energy', 'liveness', 'speechiness', 'acousticness', 'instrumentalness', 
        'danceability', 'loudness', 'valence', 'tempo'
    ];
    for (var track of tracks) {
        if (track.added_at) {
            track.date = track.added_at;
        } else {
            track.date = track.played_at;
        }
        track._artists = track.artists;
        var artistNames = [];
        for (var artist of track._artists) {
            artistNames.push(artist.name);
        }
        track.artists = artistNames;
        if (track.audio_features) {
            for (var feature of featuresToUse) {
                track[feature] = track.audio_features[feature];
            }
        } else {
            // console.log("error: track " + track.name + " has no features", track);
        }
    }
    return tracks;
}

async function library() {
    // First, get all the songs in the library
    var tracks = await savedTracks();
    // Get features for all tracks
    var features = await featurizeTracks(tracks);
    // Coalesce tracks and features
    for (var idx in tracks) {
        tracks[idx].audio_features = features[tracks[idx].id];
    }
    // Get artist genres for all tracks
    var genres = await genresForTracks(tracks);
    for (var idx in tracks) {
        tracks[idx].genres = genres[idx];
    }

    var formattedTracks = await formatTracksForViz(tracks);

    return formattedTracks;
}

async function topArtists() {
    var timeRanges = ["short_term", "medium_term", "long_term"];
    var ret = {}
    for (var timeRange of timeRanges) {
        var artists = await callWithRetry(
            () => {return spotifyApi.getMyTopArtists({"limit": 50, "time_range": timeRange})}
        ).then(function(response) {
            response.body.artists = response.body.items;
            return response;
        }).then(unpackArtistsResponse);
        ret[timeRange] = artists;
    }
    return ret;
}

async function topTracks() {
    var timeRanges = ["short_term", "medium_term", "long_term"];
    var ret = {}
    for (var timeRange of timeRanges) {
        var tracks = await callWithRetry(
            () => {return spotifyApi.getMyTopTracks({"limit": 50, "time_range": timeRange})}
        ).then(
            function (response) {
                for (var i in response.body.items) {
                    newItem = {
                        "track": response.body.items[i],
                    }
                    response.body.items[i] = newItem;
                }

                console.log("Formatted top tracks: ", response.body.items);
                return response;
            }
        ).then(unpackTracksResponse);
        console.log("top tracks: ", tracks);
        var features = await featurizeTracks(tracks);
        console.log("features for top tracks: ", features);
        // Coalesce tracks and features
        for (var idx in tracks) {
            tracks[idx].audio_features = features[idx];
        }
        // Get artist genres for all tracks
        var genres = await genresForTracks(tracks);
        for (var idx in tracks) {
            tracks[idx].genres = genres[idx];
        }
        var formattedTracks = await formatTracksForViz(tracks);
        ret[timeRange] = formattedTracks;
    }
    return ret;
}

async function recentlyPlayed() {
    var tracks = await callWithRetry(
        () => {return spotifyApi.getMyRecentlyPlayedTracks({"limit": 50})}
    ).then(unpackTracksResponse);
    var features = await featurizeTracks(tracks);
    // Coalesce tracks and features
    for (var idx in tracks) {
        tracks[idx].audio_features = features[idx];
    }
    // Get artist genres for all tracks
    var genres = await genresForTracks(tracks);
    for (var idx in tracks) {
        tracks[idx].genres = genres[idx];
    }
    var formattedTracks = await formatTracksForViz(tracks);
    return formattedTracks;
}

async function profile() {
    return (await callWithRetry(() => {return spotifyApi.getMe()})).body;
}

async function libraryFeatures(offset, limit) {
    var tracksResults = callWithRetry(() => {
        return spotifyApi.getMySavedTracks({"offset": offset, "limit": limit});
    });
    var featuresResults = tracksResults.then(
        function (response) {
            var tracks = response.body.items;
            var ids = [];
            for (var i in tracks) {
                ids.push(tracks[i].track.id);
            }
            return callWithRetry(() => {
                return spotifyApi.getAudioFeaturesForTracks(ids).then(
                    function (r) {
                        var features = r.body.audio_features;
                        var ret = [];
                        for (var i in features) {
                            var track = tracks[i];
                            track.audio_features = features[i];
                            ret.push(track);
                        }
                        return ret;
                    }
                );
            });
        }
    );
    var genresResults = featuresResults.then(
        function (tracks) {
            var promises = [];
            var artistIds = [];
            for (var i in tracks) {
                var artists = tracks[i].track.artists;
                for (var j in artists) {
                    artistIds.push(artists[j].id);
                }
                // Call /v1/artists
                // promises.push(callWithRetry(() => {return spotifyApi.getArtists(artistIds)}));
            }
            var artistTotal = artistIds.length;
            var numCalls = parseInt(artistTotal / 50) + 1;
            var promises = [];
            for (var i = 0; i < numCalls; i++) {
                var ids = artistIds.slice(i * 50, (i + 1) * 50);
                if (ids.length > 0) {
                    console.log("getting genres for" + ids.length + "artists");
                    promises.push(callWithRetry(() => {return spotifyApi.getArtists(ids)}));
                }
            }
            return Promise.all(promises).then(
                function (artistResponses) {
                    var artistIdx = 0;
                    var responseIdx = 0;
                    var ret = [];
                    for (var i in tracks) {
                        var trackArtists = tracks[i].track.artists;
                        // convert i and j to index in artistResponses
                        if (artistIdx >= 50) {
                            artistIdx %= 50;
                            responseIdx += 1
                        }
                        var response = artistResponses[responseIdx];
                        var artists = response.body.artists.slice(artistIdx, artistIdx + trackArtists.length);
                        var genres = [];
                        for (var j in artists) {
                            for (var k in artists[j].genres) {
                                genres.push(artists[j].genres[k]);
                            }
                        }
                        var track = tracks[i];
                        track.genres = genres;
                        ret.push(track);

                        artistIdx += artists.length;
                    }
                    return ret;
                }
            );
        }
    )
    return genresResults;
    return Promise.all([featuresResults, genresResults]).then(
        function(res) {
            var features = res[0];
            var genres = res[1];
            var ret = []
            for (var i in features) {
                ret.push(
                    {
                        "track": features.track,
                        "audio_feature": features.audio_feature,
                        "genres": genres.genres,
                    }
                );
            }
        }
    );
}

function loadPage() {
    initApi();
    Promise.all([
        library(),
        topArtists(),
        topTracks(),
        recentlyPlayed(),
        profile()
    ]).then(
        function (data) {
            console.log("loaded all data");
            console.log("library:", data[0]);
            console.log("top artists:", data[1]);
            console.log("top tracks:", data[2]);
            console.log("recently played:", data[3]);
            console.log("profile:", data[4]);
            console.log(viz);
            viz.data.songDataGlobal = data[0];
            window.localStorage.setItem("library", pako.deflate(JSON.stringify(data[0])));
            // window.localStorage.setItem("libraryBig", JSON.stringify(data[0]));
            viz.data.topArtistsGlobal = data[1];
            viz.data.topTracksGlobal = data[2];
            viz.data.recentlyPlayedGlobal = data[3];
            viz.data.userProfileGlobal = data[4];
            viz.loadPage();
        }, function (error) {
            console.log("error!");
            console.log(error);
        }
    )
}

var urlQuery = window.location.search;
var urlParams = new URLSearchParams(urlQuery);

// Check cookies for auth information
var code_challenge = Cookies.get("code_challenge");
var code_verifier = Cookies.get("code_verifier");

var access_token = Cookies.get("access_token");
var refresh_token = Cookies.get("refresh_token");

if (access_token || refresh_token) {
    if (window.location.href == redirectUri) {
        window.location.href = "/viz";
    }
    var login_button = document.getElementById("login-button");
    login_button.innerHTML = "Log Out";
    login_button.onclick = logout;

    if (access_token) {
        console.log("have access token: " + access_token);
        loadPage();
    } else if (refresh_token) {
        console.log("need to refresh with: " + refresh_token);
        auth().then(() => {
            console.log("auth completed");
            loadPage();
        });
    } 
} else {
    if (code_challenge && code_verifier) {
        auth().then(() => {
                console.log("auth completed");
                window.location.href = "/viz";
            }
        );
    } else {
        console.log("need to complete auth!");
        var login_button = document.getElementById("login-button");
        login_button.innerHTML = "Log In";
        login_button.onclick = auth;
    }
}