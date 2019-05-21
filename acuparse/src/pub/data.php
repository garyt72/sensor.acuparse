<?php
$array = [];
$moon = [];

require(dirname(__DIR__) . '/inc/loader.php');

// get timestamp for current conditions:
$result = mysqli_fetch_assoc(mysqli_query($conn, "SELECT `timestamp` FROM `windspeed` ORDER BY `timestamp` DESC LIMIT 1"));

require(APP_BASE_PATH . '/fcn/weather/getCurrentWeatherData.php');
$getCurrent = new getCurrentWeatherData();
$array['current']	= (array) $getCurrent->getConditions();
$array['current']['timestamp'] = $result['timestamp'];

require(APP_BASE_PATH . '/fcn/weather/getArchiveWeatherData.php');
$getArchive = new getArchiveWeatherData();
$array['yesterday']	= $getArchive->getYesterday();
$array['this_week']	= $getArchive->getWeek();
$array['this_month']	= $getArchive->getMonth();
$array['last_month']	= $getArchive->getLastMonth();
$array['this_year']	= $getArchive->getYear();
$array['all_time']	= $getArchive->getAllTime();

// Get Moon Data:
require(APP_BASE_PATH . '/pub/lib/mit/moon/moonphase.php');
$getMoon = new MoonPhase();
$moon['age'] = round($getMoon->age(), 1);
$moon['stage'] = $getMoon->phase_name();
$moon['next_new'] = date('j M @ H:i', $getMoon->next_new_moon());
$moon['next_full'] = date('j M @ H:i', $getMoon->next_full_moon());
$moon['last_new'] = date('j M @ H:i', $getMoon->new_moon());
$moon['last_full'] = date('j M @ H:i', $getMoon->full_moon());
$moon['distance'] = $getMoon->distance();
$moon['illumination'] = round($getMoon->illumination()*100, 0);
$moon['icon_url'] = "/local/moon/" . (round($getMoon->age(), 0)) . ".gif";
$moon['timestamp'] = $result['timestamp'];


$array['moon'] = $moon;

if ($config->station->towers === true) {
	$result = mysqli_query($conn, "SELECT * FROM `towers` ORDER BY `arrange`");

	if (is_object($result) && $result->num_rows > 0)
	{
		while($row = mysqli_fetch_assoc($result))
		{
			$sensorID   = $row['sensor'];
			$sensorName = $row['name'];

			$result2 = mysqli_fetch_assoc(mysqli_query($conn, "SELECT * FROM `tower_data` WHERE `sensor` = '$sensorID' ORDER BY `timestamp` DESC LIMIT 1"));
 
 			$sensorArray = [];

			$sensorArray['tempF']	  = $result2['tempF'];
			$sensorArray['relH']	  = $result2['relH'];
			$sensorArray['timestamp'] = $result2['timestamp'];

			$array['current'][$sensorName] = $sensorArray;
		}
	}
}

if(!isset($_GET['json']) && !isset($_GET['JSON']))
{
	echo "<pre>";
	print_r($array);
	echo "</pre>";
}
else
{
	echo json_encode($array);
}
die();
?>
