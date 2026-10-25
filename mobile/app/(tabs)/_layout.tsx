import { Ionicons } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import type { ComponentProps } from 'react';
import { Image, Pressable, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useColors } from '../../src/theme-context';

function PetLensHeader() {
  const colors = useColors();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 9 }}>
      <Image
        accessibilityLabel="PetLens analysis for dogs"
        source={require('../../assets/petlens-dog-mark.png')}
        style={{ width: 42, height: 42, borderRadius: 13, backgroundColor: 'transparent' }}
      />
      <View>
        <Text style={{ color: colors.text, fontSize: 16, fontWeight: '800' }}>PetLens</Text>
        <Text style={{ color: colors.muted, fontSize: 9, letterSpacing: 1.1 }}>ANALYSIS FOR DOGS</Text>
      </View>
    </View>
  );
}

type FloatingTabBarProps = Parameters<NonNullable<ComponentProps<typeof Tabs>['tabBar']>>[0];

// The stock tab bar ignores horizontal insets on Android, so the floating pill is drawn here.
function FloatingTabBar({ state, descriptors, navigation }: FloatingTabBarProps) {
  const colors = useColors();
  const insets = useSafeAreaInsets();
  return (
    <View
      style={{
        position: 'absolute',
        left: 15,
        right: 15,
        bottom: Math.max(12, insets.bottom + 8),
        flexDirection: 'row',
        padding: 6,
        backgroundColor: 'rgba(6,24,38,0.96)',
        borderWidth: 1,
        borderColor: 'rgba(22,105,170,0.4)',
        borderRadius: 22,
        elevation: 12,
      }}
    >
      {state.routes.map((route, index) => {
        const { options } = descriptors[route.key];
        // Settings stays routable but is opened from elsewhere, not from the tab bar.
        if (route.name === 'settings') return null;
        const focused = state.index === index;
        const color = focused ? '#ffffff' : colors.muted;
        return (
          <Pressable
            key={route.key}
            accessibilityRole="button"
            accessibilityState={{ selected: focused }}
            accessibilityLabel={String(options.title ?? route.name)}
            onPress={() => {
              const event = navigation.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
              if (!focused && !event.defaultPrevented) navigation.navigate(route.name, route.params);
            }}
            style={{
              flex: 1,
              alignItems: 'center',
              justifyContent: 'center',
              gap: 4,
              paddingVertical: 10,
              borderRadius: 16,
              backgroundColor: focused ? 'rgba(55,148,164,0.2)' : 'transparent',
            }}
          >
            {options.tabBarIcon?.({ focused, color, size: 24 })}
            <Text numberOfLines={1} style={{ color, fontSize: 11, fontWeight: '700' }}>
              {options.title ?? route.name}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export default function TabsLayout() {
  const colors = useColors();
  return (
    <Tabs
      tabBar={(props) => <FloatingTabBar {...props} />}
      screenOptions={{
        headerStyle: { backgroundColor: colors.background },
        headerShadowVisible: false,
        headerTintColor: colors.text,
        headerTitleStyle: { fontWeight: '700' },
        headerTitle: PetLensHeader,
        headerRightContainerStyle: { paddingRight: 18 },
        headerLeftContainerStyle: { paddingLeft: 6 },
        sceneStyle: { backgroundColor: colors.background, paddingBottom: 112 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Overview',
          tabBarIcon: ({ color, size }) => <Ionicons name="pulse-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="analyze"
        options={{
          title: 'New analysis',
          tabBarIcon: ({ color, size }) => <Ionicons name="add-circle-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: 'History',
          tabBarIcon: ({ color, size }) => <Ionicons name="time-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="pet/index"
        options={{
          title: 'Pet profile',
          tabBarIcon: ({ color, size }) => <Ionicons name="paw-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          href: null,
        }}
      />
    </Tabs>
  );
}
