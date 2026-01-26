<?xml version='1.0' encoding='UTF-8'?>
<Project Type="Project" LVVersion="25008000">
	<Property Name="NI.LV.All.SaveVersion" Type="Str">25.0</Property>
	<Property Name="NI.LV.All.SourceOnly" Type="Bool">true</Property>
	<Item Name="My Computer" Type="My Computer">
		<Property Name="NI.SortType" Type="Int">3</Property>
		<Property Name="server.app.propertiesEnabled" Type="Bool">true</Property>
		<Property Name="server.control.propertiesEnabled" Type="Bool">true</Property>
		<Property Name="server.tcp.enabled" Type="Bool">false</Property>
		<Property Name="server.tcp.port" Type="Int">0</Property>
		<Property Name="server.tcp.serviceName" Type="Str">My Computer/VI Server</Property>
		<Property Name="server.tcp.serviceName.default" Type="Str">My Computer/VI Server</Property>
		<Property Name="server.vi.callsEnabled" Type="Bool">true</Property>
		<Property Name="server.vi.propertiesEnabled" Type="Bool">true</Property>
		<Property Name="specify.custom.address" Type="Bool">false</Property>
		<Item Name="BattLoad.vi" Type="VI" URL="../BattLoad.vi"/>
		<Item Name="CalcAhWh.vi" Type="VI" URL="../CalcAhWh.vi"/>
		<Item Name="Calibrate.vi" Type="VI" URL="../Calibrate.vi"/>
		<Item Name="Config.ctl" Type="VI" URL="../Config.ctl"/>
		<Item Name="GetPicoMsg.vi" Type="VI" URL="../GetPicoMsg.vi"/>
		<Item Name="Globals.vi" Type="VI" URL="../Globals.vi"/>
		<Item Name="LoadConfig.vi" Type="VI" URL="../LoadConfig.vi"/>
		<Item Name="LoadData.vi" Type="VI" URL="../LoadData.vi"/>
		<Item Name="Mode.ctl" Type="VI" URL="../Mode.ctl"/>
		<Item Name="Range.ctl" Type="VI" URL="../Range.ctl"/>
		<Item Name="SaveConfig.vi" Type="VI" URL="../SaveConfig.vi"/>
		<Item Name="State.ctl" Type="VI" URL="../State.ctl"/>
		<Item Name="TstRegExp.vi" Type="VI" URL="../TstRegExp.vi"/>
		<Item Name="BackupFile.vi" Type="VI" URL="../BackupFile.vi"/>
		<Item Name="1CellLog.vi" Type="VI" URL="../1CellLog.vi"/>
		<Item Name="LM235_Conv.vi" Type="VI" URL="../LM235_Conv.vi"/>
		<Item Name="Dependencies" Type="Dependencies"/>
		<Item Name="Build Specifications" Type="Build">
			<Item Name="BattCapacity" Type="EXE">
				<Property Name="App_copyErrors" Type="Bool">true</Property>
				<Property Name="App_INI_aliasGUID" Type="Str">{BE836C63-DA5A-4D89-A7B5-4753775F6475}</Property>
				<Property Name="App_INI_GUID" Type="Str">{9507FD52-B7BE-41C7-8A03-D862EBFFE934}</Property>
				<Property Name="App_serverConfig.httpPort" Type="Int">8002</Property>
				<Property Name="App_serverType" Type="Int">0</Property>
				<Property Name="App_winsec.description" Type="Str">http://www.Retired.com</Property>
				<Property Name="Bld_autoIncrement" Type="Bool">true</Property>
				<Property Name="Bld_buildCacheID" Type="Str">{FB66999A-0D15-4816-B849-6EEFE91DFF4B}</Property>
				<Property Name="Bld_buildSpecName" Type="Str">BattCapacity</Property>
				<Property Name="Bld_excludeInlineSubVIs" Type="Bool">true</Property>
				<Property Name="Bld_excludeLibraryItems" Type="Bool">true</Property>
				<Property Name="Bld_excludePolymorphicVIs" Type="Bool">true</Property>
				<Property Name="Bld_localDestDir" Type="Path">../builds/NI_AB_PROJECTNAME/BattCapacity</Property>
				<Property Name="Bld_localDestDirType" Type="Str">relativeToCommon</Property>
				<Property Name="Bld_modifyLibraryFile" Type="Bool">true</Property>
				<Property Name="Bld_previewCacheID" Type="Str">{4BBA27A7-1546-4E03-A868-DC025C690DB8}</Property>
				<Property Name="Bld_version.build" Type="Int">13</Property>
				<Property Name="Bld_version.major" Type="Int">1</Property>
				<Property Name="Destination[0].destName" Type="Str">BattCapacity.exe</Property>
				<Property Name="Destination[0].path" Type="Path">../builds/NI_AB_PROJECTNAME/BattCapacity/BattCapacity.exe</Property>
				<Property Name="Destination[0].preserveHierarchy" Type="Bool">true</Property>
				<Property Name="Destination[0].type" Type="Str">App</Property>
				<Property Name="Destination[1].destName" Type="Str">Support Directory</Property>
				<Property Name="Destination[1].path" Type="Path">../builds/NI_AB_PROJECTNAME/BattCapacity/data</Property>
				<Property Name="DestinationCount" Type="Int">2</Property>
				<Property Name="Source[0].itemID" Type="Str">{DE06B16F-AE56-4FFE-A185-0B71EECFD45D}</Property>
				<Property Name="Source[0].type" Type="Str">Container</Property>
				<Property Name="Source[1].destinationIndex" Type="Int">0</Property>
				<Property Name="Source[1].itemID" Type="Ref">/My Computer/BattLoad.vi</Property>
				<Property Name="Source[1].sourceInclusion" Type="Str">TopLevel</Property>
				<Property Name="Source[1].type" Type="Str">VI</Property>
				<Property Name="SourceCount" Type="Int">2</Property>
				<Property Name="TgtF_companyName" Type="Str">Retired</Property>
				<Property Name="TgtF_fileDescription" Type="Str">BattCapacity</Property>
				<Property Name="TgtF_internalName" Type="Str">BattCapacity</Property>
				<Property Name="TgtF_legalCopyright" Type="Str">Copyright © 2026 Retired</Property>
				<Property Name="TgtF_productName" Type="Str">BattCapacity</Property>
				<Property Name="TgtF_targetfileGUID" Type="Str">{B052697F-DD95-4858-9056-48B501CDDD28}</Property>
				<Property Name="TgtF_targetfileName" Type="Str">BattCapacity.exe</Property>
				<Property Name="TgtF_versionIndependent" Type="Bool">true</Property>
			</Item>
		</Item>
	</Item>
</Project>
